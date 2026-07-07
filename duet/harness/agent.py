"""The one primitive: an agent that runs an internal ReAct loop, and a helper to
continue it with one more turn. This is the ONLY place an LLM is called.

`run_agent` takes a system prompt + a user-side message list, runs (model -> optional
tool calls -> observe -> ...) until the model stops, hits its TOOL-CALL BUDGET B, trips
the repeated-action guard, or hits the runaway step backstop, and returns the final
text plus the full transcript. `continue_agent` appends one user message to a finished
agent's transcript and does a single no-tool call — this is how a shift, having spent
its budget, is asked (with its full working memory intact) for the hand-off note, and
how the last shift is forced to commit. Keeping continuation here preserves "run_agent
is the only LLM caller" and gives the wrap-up its own delimited user message (hygiene
rule 3).

Two independent budgets, do not conflate them:
  - tool_budget B (int): the SHIFT budget. Forces the hand-off once B tool calls are
    spent, so "when to hand off" is never a confound (PLAN, relay mechanic 1).
  - usd_budget (Budget): a per-TASK USD safety cap shared across all shifts; a runaway
    task latches `exceeded` and the topology short-circuits to an honest UNKNOWN.

The model is reached through the shared Tinker proxy route (/m/<tag>/v1): the client
speaks plain OpenAI chat.completions with model 'gpt-4o' (aliased upstream to
Qwen/Qwen3.6-35B-A3B); the proxy converts Qwen's text tool-calls into structured
tool_calls, and strips the <think> trace — so prompts carry NO chain-of-thought
scaffolding and we get a normal OpenAI tool loop here.
"""
import os
from dataclasses import dataclass, field

import prompts
from tools import tool_specs, run_tool

MAX_INNER_STEPS = 40    # runaway backstop, NOT the budget — B stops a healthy shift first
TEMPERATURE = 0.0
REPEAT_LIMIT = 3        # identical (tool,args) calls in a row -> the agent is thrashing; stop

# Output-length budget. The proxy defaults calls to its own cap; on a thinking model the
# whole budget can be spent in the reasoning trace, truncating the reply before its
# terminal line. We set our own cap, sized ADAPTIVELY so prompt+output never exceeds the
# model context (a growing tool history shrinks the room gracefully, not a hard 400).
MODEL_CTX = int(os.environ.get("DUET_MODEL_CTX", "64000"))
# 28k, matching camel's proven regime. Qwen3.6's think trace counts against max_tokens, so
# an 8k cap truncates hard GAIA reasoning BEFORE the FINAL ANSWER line — a cascade of
# 'length' no_answers that pollute the mechanism study (observed on gaia_ebbc1f13 at 8k).
# The proxy default (TINKER_MAX_TOKENS=8000) only applies when a caller omits max_tokens;
# we always set it via _max_tokens_for, so this value wins and degrades adaptively when a
# large tool history shrinks the context room.
MAX_OUTPUT_TOKENS = int(os.environ.get("DUET_MAX_TOKENS", "28000"))
_CTX_MARGIN = 2048

# Proactive context bound (long GAIA tool loops): the loop re-sends the whole growing
# tool history each step, so input creeps toward the wall. Compact LAZILY — only once the
# prompt crosses a high-watermark — by stubbing the OLDEST tool results first, down to a
# low-watermark that still leaves output room. The gap is hysteresis (avoids re-compacting
# every call). Headrooms are "tokens to reserve for output".
_COMPACT_TRIGGER_HEADROOM = int(os.environ.get("DUET_COMPACT_TRIGGER", "8000"))
_COMPACT_TARGET_HEADROOM = int(os.environ.get("DUET_COMPACT_TARGET", "16000"))
_STUB_PREFIX = "[elided] "

MAX_TOOL_CHARS = 6000   # cap a web/tool result: one big fetched page can exceed the ctx
FILE_TOOL_CHARS = 45000  # read_file returns the task's OWN attachment — don't clip data rows
_FILE_TOOLS = {"read_file"}

# The proxy replaces a think-truncated reply (finish=='length' with no closing </think>) with
# this EXACT sentinel string (shared/proxy/server.py). Because it is non-empty, a naive
# "retry only when content is empty" guard would accept it as a real answer. We detect it
# explicitly so the wrap-up treats it as no-output and re-asks instead of crossing it.
PROXY_TRUNCATION_SENTINEL = (
    "[the model could not finish reasoning within the token budget; no action produced this turn]"
)


def _usable_text(content):
    """A wrap-up reply is usable only if it is non-empty AND not the proxy's think-truncation
    sentinel. Empty = the model emitted only a <tool_call>/think trace (proxy left content
    null); sentinel = it spent the whole budget reasoning without ever answering."""
    c = (content or "").strip()
    return bool(c) and c != PROXY_TRUNCATION_SENTINEL


def _est_prompt_tokens(messages):
    """Cheap char/4 estimate (no tiktoken in env); only used to leave output headroom,
    so a rough over-estimate is the safe direction."""
    chars = 0
    for m in messages:
        c = m.get("content")
        chars += len(c) if isinstance(c, str) else 0
        for tc in m.get("tool_calls") or []:
            chars += len(((tc.get("function") or {}).get("arguments")) or "")
    return chars // 4


def _max_tokens_for(messages):
    room = MODEL_CTX - _est_prompt_tokens(messages) - _CTX_MARGIN
    return max(2048, min(MAX_OUTPUT_TOKENS, room))


def _truncate(s, cap=MAX_TOOL_CHARS):
    s = s or ""
    return s if len(s) <= cap else s[:cap] + f"\n…[truncated {len(s) - cap} chars]"


def _tool_call_index(messages):
    """tool_call_id -> 'name(arg-slice)', so an evicted result leaves a re-fetchable
    pointer the agent can re-issue if it still needs it."""
    idx = {}
    for m in messages:
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function") or {}
            idx[tc.get("id")] = f"{fn.get('name', 'tool')}({(fn.get('arguments') or '')[:60]})"
    return idx


def _bound_context(messages, trigger_headroom=_COMPACT_TRIGGER_HEADROOM,
                   target_headroom=_COMPACT_TARGET_HEADROOM):
    """Lazily bound the prompt: no-op until est. prompt crosses the high-watermark, then
    replace the OLDEST not-yet-stubbed tool results with a one-line re-fetchable stub,
    oldest-first, until under the low-watermark. The freshest tool result is kept whole."""
    if _est_prompt_tokens(messages) <= MODEL_CTX - trigger_headroom:
        return
    idx = _tool_call_index(messages)
    tool_pos = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    keep_last = tool_pos[-1] if tool_pos else None
    for i in tool_pos:
        if _est_prompt_tokens(messages) <= MODEL_CTX - target_headroom:
            break
        m = messages[i]
        if i == keep_last or (m.get("content") or "").startswith(_STUB_PREFIX):
            continue
        orig = m.get("content") or ""
        label = idx.get(m.get("tool_call_id"), "tool result")
        m["content"] = f"{_STUB_PREFIX}{label} -> {len(orig)} chars elided to free context"


def _compact_for_wrapup(messages):
    """Return a COPY of `messages` with every tool result except the most recent stubbed,
    for a wrap-up call (the hand-off note / forced commit). Unlike `_bound_context` this is
    unconditional: a *reflective* ask ("summarize what you established") over many RAW tool
    dumps makes Qwen3.6 re-read and re-analyze all of them and spiral past the token cap inside
    <think>, yielding the proxy's truncation sentinel and NO note — even when the context is
    small enough that lazy compaction never triggers (observed on gaia_983bba7c: ~12k prompt,
    still 'length'). Stubbing the dumps forces the note to be written from the worker's own
    memory of what it found — which is exactly what a real hand-off is — not by re-deriving
    from every fetched page. The freshest tool result is kept whole (the evidence in hand).

    NON-MUTATING by design: the wrap-up call should not see the raw dumps, but the SAVED
    transcript must still keep them (else the audit trail — what the worker actually observed —
    is destroyed; the very thing that makes a wrong hand-off diagnosable). So we copy rather
    than stub in place, and the caller sends the copy but stores the originals. Every tool
    message is shallow-copied (so no tool dict is shared with the original and a later
    `_bound_context` on the copy can't reach back); other messages pass through by reference.
    Idempotent: already-stubbed results are left as-is."""
    idx = _tool_call_index(messages)
    tool_pos = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    keep_last = tool_pos[-1] if tool_pos else None
    out = []
    for i, m in enumerate(messages):
        if m.get("role") != "tool":
            out.append(m)
            continue
        m = dict(m)                                   # copy: never mutate the stored dict
        content = m.get("content") or ""
        if i != keep_last and not content.startswith(_STUB_PREFIX):
            label = idx.get(m.get("tool_call_id"), "tool result")
            m["content"] = (f"{_STUB_PREFIX}{label} -> {len(content)} chars elided; "
                            "write your note from memory, do not re-fetch")
        out.append(m)
    return out


def _is_context_overflow(e):
    s = str(e).lower()
    return "context" in s or "exceeds" in s or "max_tokens" in s


class Budget:
    """Per-task USD spend cap, shared across a topology's agents. Charged live from each
    response's usage; once `spent` crosses `cap`, `exceeded` latches True and the topology
    short-circuits to an honest UNKNOWN rather than thrashing. A falsy cap = unlimited."""

    def __init__(self, cap_usd, prefill_per_mtok, sample_per_mtok):
        self.cap = cap_usd or 0.0
        self.prefill = prefill_per_mtok
        self.sample = sample_per_mtok
        self.spent = 0.0
        self.exceeded = False

    def charge(self, usage):
        if usage is not None:
            self.spent += ((getattr(usage, "prompt_tokens", 0) or 0) / 1e6 * self.prefill
                           + (getattr(usage, "completion_tokens", 0) or 0) / 1e6 * self.sample)
        if self.cap and self.spent >= self.cap:
            self.exceeded = True
        return self.exceeded


@dataclass
class AgentResult:
    role: str
    final: str = ""                  # the agent's terminal text (its published artifact)
    n_steps: int = 0                 # model calls in the inner loop (+ any continuation)
    n_tool_calls: int = 0
    transcript: list = field(default_factory=list)   # full message list incl. tool I/O
    finish: str = "stop"             # stop | budget | loop | length | step_cap | ctx_overflow

    @property
    def truncated(self):
        """True when the agent did NOT cleanly produce its terminal text — it hit the
        token cap, the step backstop, or context overflowed. Such a reply is unlikely to
        carry a usable artifact; the topology substitutes a marker rather than crossing
        raw unterminated reasoning over an edge (hygiene rule 6)."""
        return self.finish in ("length", "step_cap", "ctx_overflow")

    @property
    def has_final_answer(self):
        return "FINAL ANSWER:" in (self.final or "")


def _wire_messages(messages):
    """The message list as the UPSTREAM should see it. Drops harness-only annotation keys
    that we keep on the stored transcript but must NOT resend: `reasoning_content` (the
    model's own recovered <think> trace — resending past CoT would balloon prompt tokens and
    perturb behaviour, and some backends 400 on the unknown field). Cheap shallow copies; the
    stored `messages` keep every annotation."""
    return [{k: v for k, v in m.items() if k != "reasoning_content"} for m in messages]


def _call(client, model, messages, specs, usd_budget, cap=None):
    """One model call with lazy context-bounding + a single compact-and-retry on overflow.
    Returns (message, finish_reason, over_budget). On unrecoverable overflow, returns a
    synthetic (None, 'ctx_overflow', over_budget). `cap`, if given, is an explicit hard
    ceiling on output tokens (min'd with the adaptive room) — the wrap-up uses a small cap so
    a think-spiral hits 'length' cheaply instead of burning the full context (a clean note is
    ~1.5k tokens; a spiral would otherwise waste ~28k)."""
    def _mt():
        room = _max_tokens_for(messages)
        return min(room, cap) if cap else room
    _bound_context(messages)
    try:
        resp = client.chat.completions.create(
            model=model, messages=_wire_messages(messages), tools=specs, temperature=TEMPERATURE,
            stream=False, max_tokens=_mt())
    except Exception as e:
        if not _is_context_overflow(e):
            raise
        _bound_context(messages, trigger_headroom=MODEL_CTX, target_headroom=MODEL_CTX // 2)
        try:
            resp = client.chat.completions.create(
                model=model, messages=_wire_messages(messages), tools=specs, temperature=TEMPERATURE,
                stream=False, max_tokens=_mt())
        except Exception:
            return None, "ctx_overflow", False
    over = usd_budget.charge(getattr(resp, "usage", None)) if usd_budget is not None else False
    return resp.choices[0].message, resp.choices[0].finish_reason, over


def _reasoning_of(msg):
    """The model's recovered <think> chain-of-thought for this reply, if the proxy surfaced
    one. The Tinker route strips the inline <think>…</think> from `content` and re-attaches it
    as `reasoning_content` (lands in the SDK object's model_extra). None when the reply had no
    visible think block (e.g. a truncated 'length' turn with no closing </think>)."""
    r = getattr(msg, "reasoning_content", None)
    if r is None:
        extra = getattr(msg, "model_extra", None) or {}
        r = extra.get("reasoning_content")
    return (r or None)


def _assistant_dict(msg, drop_tool_calls=False):
    """Build the stored assistant turn: content, its recovered CoT (reasoning_content), and —
    unless suppressed — the tool_calls (so a later call sees its own calls). `drop_tool_calls`
    is used by the wrap-up, which offers no tools: any <tool_call> the model emits there is
    unhonored and must not dangle without a matching tool response."""
    a = {"role": "assistant", "content": msg.content}
    r = _reasoning_of(msg)
    if r:
        a["reasoning_content"] = r
    if msg.tool_calls and not drop_tool_calls:
        a["tool_calls"] = [{"id": tc.id, "type": "function",
                            "function": {"name": tc.function.name,
                                         "arguments": tc.function.arguments}}
                           for tc in msg.tool_calls]
    return a


def _record_assistant(messages, msg):
    """Append the assistant turn verbatim (so a later call sees its own tool_calls)."""
    messages.append(_assistant_dict(msg))


def _sig(tc):
    return (tc.function.name, (tc.function.arguments or "").strip())


def run_agent(role, system_prompt, task_messages, tool_names, client, model,
              addon, tool_budget=None, budget_tool_names=None,
              max_inner_steps=MAX_INNER_STEPS, usd_budget=None, env=None,
              resume=None) -> AgentResult:
    """Run one agent's internal loop and return its AgentResult.

    `task_messages` is the user-side context (task + any hand-off note / shared-state).
    `addon.inject_context` may prepend the shared-state block (vanilla: no-op). `env` is
    the per-task stateful world (pddl) that env-tool calls route to. The loop stops when
    the model stops calling tools (clean), spends `tool_budget` budget-counted tool calls
    (forced = 'budget'), repeats one call REPEAT_LIMIT times ('loop'), or hits a
    truncation/backstop. A forced/truncated stop leaves NO terminal answer — the caller
    decides the wrap-up (continue_agent) or substitutes a marker.

    `budget_tool_names`: if None, every tool call counts toward `tool_budget`; else only
    calls with those names count (PDDL bills 'pddl_step' env steps, not free observe/actions
    lookups — PLAN relay mechanic 1). All calls are always metered in `n_tool_calls`.

    `resume`: a PERSISTENT message list from this agent's previous turns (dialogue
    topology) — used verbatim instead of building [system]+task_messages, so the agent
    keeps its whole working memory across turns. The caller appends the new incoming
    user messages before calling; `inject_context` still runs (a store re-render
    REPLACES its previous block — the arms' no-accumulation contract). Counters
    (n_steps/n_tool_calls, the budget) are per-call: each turn gets a fresh budget."""
    messages = resume if resume is not None else (
        [{"role": "system", "content": system_prompt}] + list(task_messages))
    messages = addon.inject_context(role, messages)
    base_specs = tool_specs(tool_names) or []
    extra_specs = addon.extra_tool_specs(role)
    addon_tools = {s["function"]["name"] for s in extra_specs}
    specs = (base_specs + extra_specs) or None

    n_steps = n_tools = n_budget = 0
    final = ""
    finish = "step_cap"
    last_sig = None
    repeats = 0
    for _ in range(max_inner_steps):
        msg, fr, over = _call(client, model, messages, specs, usd_budget)
        if msg is None:                          # unrecoverable context overflow
            final = next((m["content"] for m in reversed(messages)
                          if m["role"] == "assistant" and m.get("content")), "")
            finish = "ctx_overflow"
            break
        n_steps += 1
        _record_assistant(messages, msg)
        calls = msg.tool_calls or []

        if not calls or over:                    # clean stop, or USD cap hit -> stop
            final = msg.content or ""
            finish = "length" if fr == "length" else "stop"
            break

        # Repeated-action guard: the same (tool,args) REPEAT_LIMIT times running = thrash.
        step_sig = tuple(sorted(_sig(tc) for tc in calls))
        repeats = repeats + 1 if step_sig == last_sig else 0
        last_sig = step_sig

        for tc in calls:                         # execute every requested tool
            name = tc.function.name
            out = (addon.run_extra_tool(name, tc.function.arguments)
                   if name in addon_tools else run_tool(name, tc.function.arguments, env=env))
            n_tools += 1
            if budget_tool_names is None or name in budget_tool_names:
                n_budget += 1
            cap = FILE_TOOL_CHARS if name in _FILE_TOOLS else MAX_TOOL_CHARS
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": _truncate(out, cap)})

        if repeats + 1 >= REPEAT_LIMIT:          # forced stop: thrashing on one action
            finish = "loop"
            break
        if tool_budget is not None and n_budget >= tool_budget:   # shift budget spent
            finish = "budget"
            break
    else:
        final = next((m["content"] for m in reversed(messages)
                      if m["role"] == "assistant" and m.get("content")), "")

    result = AgentResult(role=role, final=(final or "").strip(), n_steps=n_steps,
                         n_tool_calls=n_tools, transcript=messages, finish=finish)
    addon.on_turn_end(role, result)
    return result


WRAPUP_MAX_TRIES = 3
# The FIRST wrap-up attempt gets the full adaptive cap: a hard-but-solvable note can need a
# long think first (observed on gaia_50f58759 — its good note required >6k output; a small cap
# would regress it to a marker). RETRIES are capped cheaply: a retry after a think-spiral
# ('length' -> the proxy sentinel) deterministically re-spirals at temperature 0, so paying the
# full ~28k again is pure waste; the other retry case (an empty tool-call turn) barely thinks
# anyway. So attempt 1 buys quality, attempts 2+ stay cheap.
WRAPUP_RETRY_CAP = int(os.environ.get("DUET_WRAPUP_RETRY_CAP", "6000"))


def continue_agent(result, user_prompt, client, model, addon, usd_budget=None) -> AgentResult:
    """Append one user message to a finished agent's transcript and get its terminal text.
    The wrap-up seam: the shift, holding its full working memory, is asked for a hand-off
    note (hygiene rule 3 — the request is its own delimited user message injected only now),
    or the last shift is forced to commit. This is a terminal artifact (reflection /
    decision), NOT more investigation, so no tools are offered.

    Robustness (two coupled failure modes on Qwen3.6, both fixed here):
      1. A shift cut off mid-work often tries to keep investigating — it emits a <tool_call>,
         which the proxy parses into tool_calls even though we sent no schemas, leaving the
         visible content empty.
      2. Asked to REFLECT over its raw tool dumps, the model re-analyzes all of them and
         spirals past the token cap inside <think>; the proxy returns its truncation sentinel
         (finish=='length'), a NON-empty string that must not be mistaken for a real note.
    We first `_compact_for_wrapup` (stub old tool dumps -> no spiral), then loop: any reply
    that is empty, the sentinel, or a truncated ('length') generation is NOT honored — we
    record it text-only (dropping unhonored tool_calls so ordering stays valid) and re-ask,
    firmly, for plain prose (up to WRAPUP_MAX_TRIES). If it never writes usable text, `.final`
    is '' and finish carries the last failure so the caller substitutes a marker (raw
    reasoning / a blank / a truncated stub must never cross an edge — rule 6)."""
    # Two views of the same conversation. `record` is the real transcript we STORE — it keeps
    # the raw tool observations (the audit trail). `wire` is a stubbed copy we SEND, so the
    # reflective ask can't spiral over raw dumps. Each wrap-up turn is appended to BOTH.
    record = result.transcript
    wire = _compact_for_wrapup(record)
    user_msg = {"role": "user", "content": user_prompt}
    record.append(user_msg); wire.append(user_msg)
    n_extra = 0
    final, finish = "", "stop"
    for attempt in range(WRAPUP_MAX_TRIES):
        if usd_budget is not None and usd_budget.exceeded:
            finish = "budget"
            break
        cap = None if attempt == 0 else WRAPUP_RETRY_CAP   # full quality first, cheap retries
        msg, fr, _ = _call(client, model, wire, None, usd_budget, cap=cap)
        n_extra += 1
        if msg is None:
            finish = "ctx_overflow"
            break
        # text-only: any tool_calls the model emitted are dropped (unhonored), so message
        # ordering stays valid across retries (no dangling tool_calls awaiting a response).
        # The stored turn keeps its recovered CoT; `_call` strips reasoning_content before it
        # ever reaches the wire, so the same dict is safe to share with `wire`.
        a = _assistant_dict(msg, drop_tool_calls=True)
        record.append(a); wire.append(a)
        finish = "length" if fr == "length" else "stop"
        # Usable only if it is real text AND cleanly terminated. A 'length' generation is a
        # partial/spiralled note; retry for a clean short one rather than crossing a stub.
        if fr != "length" and _usable_text(msg.content):
            final = (msg.content or "").strip()
            break
        if attempt < WRAPUP_MAX_TRIES - 1:      # empty / sentinel / truncated -> re-ask firmly
            nudge = {"role": "user", "content": prompts.WRAPUP_NUDGE}
            record.append(nudge); wire.append(nudge)
    out = AgentResult(role=result.role, final=final, n_steps=result.n_steps + n_extra,
                      n_tool_calls=result.n_tool_calls, transcript=record, finish=finish)
    addon.on_turn_end(result.role, out)
    return out
