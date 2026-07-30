"""The one primitive: an agent that runs an internal ReAct loop, and a helper to
continue it with one more turn. This is the ONLY place an LLM is called.

Forked from multi-benchmark-eval:duet/harness/agent.py with ONE structural change:
the shift budget is a COMPLETION-TOKEN budget, not a tool-call budget. chainloss
holds the run's TOTAL generation budget fixed while varying the number of shifts N,
so the budget unit must be the thing being conserved — generated tokens (Qwen3.6's
think trace bills as completion tokens, so "thinking" spends budget too, which is
the point). Mechanics:

  - Every model call charges its `usage.completion_tokens` to the shift's
    TokenMeter (and the per-task USD safety Budget, unchanged from duet).
  - The solve loop stops issuing calls once the shift's WORK budget is spent
    (finish='budget' — the forced hand-off), and clips each call's max_tokens to
    the remaining work budget so one runaway think cannot blow the slice.
  - The wrap-up (continue_agent) is capped to the slice's remaining tokens, with a
    small floor so a note can always at least be attempted; overruns past the slice
    are therefore bounded by that floor and are LOGGED by the caller, not hidden.

All duet robustness machinery is inherited unchanged: lazy context bounding, the
unconditional wrap-up compaction (think-spiral fix), the proxy truncation sentinel,
the wrap-up retry ladder, and the repeated-action guard. The AddOn seam, PDDL env
routing, and dialogue `resume` are removed — chainloss is hard vanilla.

The model is reached through the shared Tinker proxy route (/m/<tag>/v1): the
client speaks plain OpenAI chat.completions with model 'gpt-4o' (aliased upstream
to Qwen/Qwen3.6-35B-A3B); the proxy converts Qwen's text tool-calls into structured
tool_calls, and strips the <think> trace — so prompts carry NO chain-of-thought
scaffolding and we get a normal OpenAI tool loop here.
"""
import os
from dataclasses import dataclass, field

import prompts
from tools import tool_specs, run_tool

MAX_INNER_STEPS = 40    # runaway backstop, NOT the budget — tokens stop a healthy shift first
TEMPERATURE = 0.0
REPEAT_LIMIT = 3        # identical (tool,args) calls in a row -> the agent is thrashing; stop

# Below this many remaining work tokens, don't issue another solve call: a call that
# can only be clipped mid-think produces garbage, not progress — hand off instead.
MIN_CALL_TOKENS = int(os.environ.get("CHAINLOSS_MIN_CALL_TOKENS", "768"))

# A wrap-up (note / commit) may always spend at least this much even if the slice is
# already spent — the bounded, logged overrun that guarantees an edge artifact exists.
WRAPUP_FLOOR_TOKENS = int(os.environ.get("CHAINLOSS_WRAPUP_FLOOR", "512"))

# Output-length ceiling per call, sized ADAPTIVELY so prompt+output never exceeds the
# model context (a growing tool history shrinks the room gracefully, not a hard 400).
MODEL_CTX = int(os.environ.get("CHAINLOSS_MODEL_CTX", "64000"))
MAX_OUTPUT_TOKENS = int(os.environ.get("CHAINLOSS_MAX_TOKENS", "28000"))
_CTX_MARGIN = 2048

# Proactive context bound (long tool loops): the loop re-sends the whole growing tool
# history each step, so input creeps toward the wall. Compact LAZILY — only once the
# prompt crosses a high-watermark — by stubbing the OLDEST tool results first, down to
# a low-watermark that still leaves output room. The gap is hysteresis.
_COMPACT_TRIGGER_HEADROOM = int(os.environ.get("CHAINLOSS_COMPACT_TRIGGER", "8000"))
_COMPACT_TARGET_HEADROOM = int(os.environ.get("CHAINLOSS_COMPACT_TARGET", "16000"))
_STUB_PREFIX = "[elided] "

MAX_TOOL_CHARS = 6000   # cap a web/tool result: one big fetched page can exceed the ctx

# The proxy replaces a think-truncated reply (finish=='length' with no closing </think>)
# with this EXACT sentinel string (shared/proxy/server.py). Because it is non-empty, a
# naive "retry only when content is empty" guard would accept it as a real answer.
PROXY_TRUNCATION_SENTINEL = (
    "[the model could not finish reasoning within the token budget; no action produced this turn]"
)


def _usable_text(content):
    """A wrap-up reply is usable only if it is non-empty AND not the proxy's
    think-truncation sentinel."""
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
    for a wrap-up call (the hand-off note / forced commit). Unlike `_bound_context` this
    is unconditional: a *reflective* ask ("summarize what you established") over many RAW
    tool dumps makes Qwen3.6 re-read and re-analyze all of them and spiral past the token
    cap inside <think>, yielding the proxy's truncation sentinel and NO note. Stubbing the
    dumps forces the note to be written from the worker's own memory of what it found —
    which is exactly what a real hand-off is. The freshest tool result is kept whole.

    NON-MUTATING by design: the wrap-up call should not see the raw dumps, but the SAVED
    transcript must still keep them (the audit trail the fact-survival metric reads). So
    we copy rather than stub in place; the caller sends the copy but stores the originals.
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
    """Per-task USD spend cap, shared across all shifts. Charged live from each
    response's usage; once `spent` crosses `cap`, `exceeded` latches True and the relay
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


class TokenMeter:
    """Completion-token meter — the experiment's budget unit. One per shift (the slice
    ledger) plus one per run (the total ledger); _call charges every meter it is given."""

    def __init__(self):
        self.completion = 0
        self.prompt = 0
        self.calls = 0

    def charge(self, usage):
        if usage is not None:
            self.completion += getattr(usage, "completion_tokens", 0) or 0
            self.prompt += getattr(usage, "prompt_tokens", 0) or 0
        self.calls += 1

    @property
    def spent(self):
        return self.completion


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
        carry a usable artifact; the relay substitutes a marker rather than crossing
        raw unterminated reasoning over an edge."""
        return self.finish in ("length", "step_cap", "ctx_overflow")

    @property
    def has_final_answer(self):
        return "FINAL ANSWER:" in (self.final or "")


def _wire_messages(messages):
    """The message list as the UPSTREAM should see it. Drops harness-only annotation keys
    that we keep on the stored transcript but must NOT resend: `reasoning_content` (the
    model's own recovered <think> trace — resending past CoT would balloon prompt tokens
    and perturb behaviour, and some backends 400 on the unknown field)."""
    return [{k: v for k, v in m.items() if k != "reasoning_content"} for m in messages]


def _call(client, model, messages, specs, usd_budget, meters=(), cap=None):
    """One model call with lazy context-bounding + a single compact-and-retry on overflow.
    Returns (message, finish_reason, over_budget). On unrecoverable overflow, returns a
    synthetic (None, 'ctx_overflow', over_budget). `cap`, if given, is an explicit hard
    ceiling on output tokens (min'd with the adaptive room) — the shift-budget clip, and
    the wrap-up's cheap-retry ceiling. Charges the USD safety budget AND every TokenMeter
    in `meters` from the same usage object."""
    def _mt():
        room = _max_tokens_for(messages)
        return max(1, min(room, cap)) if cap else room
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
    usage = getattr(resp, "usage", None)
    for m in meters:
        m.charge(usage)
    over = usd_budget.charge(usage) if usd_budget is not None else False
    return resp.choices[0].message, resp.choices[0].finish_reason, over


def _reasoning_of(msg):
    """The model's recovered <think> chain-of-thought for this reply, if the proxy
    surfaced one (re-attached as `reasoning_content` in the SDK object's model_extra)."""
    r = getattr(msg, "reasoning_content", None)
    if r is None:
        extra = getattr(msg, "model_extra", None) or {}
        r = extra.get("reasoning_content")
    return (r or None)


def _assistant_dict(msg, drop_tool_calls=False):
    """Build the stored assistant turn: content, its recovered CoT (reasoning_content),
    and — unless suppressed — the tool_calls. `drop_tool_calls` is used by the wrap-up,
    which offers no tools: any <tool_call> the model emits there is unhonored and must
    not dangle without a matching tool response."""
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


def run_agent(role, system_prompt, task_messages, tool_names, client, model, *,
              work_budget=None, meter=None, max_inner_steps=MAX_INNER_STEPS,
              usd_budget=None) -> AgentResult:
    """Run one agent's internal loop and return its AgentResult.

    `task_messages` is the user-side context (task + any inherited payload).
    `work_budget` is this shift's SOLVE allocation in completion tokens (its slice
    minus the wrap-up reserve — relay.py computes it); `meter` is the shift's
    TokenMeter, shared with the wrap-up so the whole slice is one ledger. The loop
    stops when the model stops calling tools (clean), the work budget is spent
    (forced = 'budget'), it repeats one call REPEAT_LIMIT times ('loop'), or hits a
    truncation/backstop. A forced/truncated stop leaves NO terminal answer — the
    caller decides the wrap-up (continue_agent) or substitutes a marker."""
    messages = [{"role": "system", "content": system_prompt}] + list(task_messages)
    meter = meter if meter is not None else TokenMeter()
    specs = tool_specs(tool_names)

    n_steps = n_tools = 0
    final = ""
    finish = "step_cap"
    last_sig = None
    repeats = 0
    for _ in range(max_inner_steps):
        remaining = None if work_budget is None else work_budget - meter.spent
        if remaining is not None and remaining < MIN_CALL_TOKENS:
            finish = "budget"                    # slice spent -> forced hand-off
            break
        msg, fr, over = _call(client, model, messages, specs, usd_budget,
                              meters=(meter,), cap=remaining)
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
            out = run_tool(tc.function.name, tc.function.arguments)
            n_tools += 1
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": _truncate(out)})

        if repeats + 1 >= REPEAT_LIMIT:          # forced stop: thrashing on one action
            finish = "loop"
            break
    else:
        final = next((m["content"] for m in reversed(messages)
                      if m["role"] == "assistant" and m.get("content")), "")

    return AgentResult(role=role, final=(final or "").strip(), n_steps=n_steps,
                       n_tool_calls=n_tools, transcript=messages, finish=finish)


WRAPUP_MAX_TRIES = 3
# The FIRST wrap-up attempt gets the slice's full remaining room: a hard-but-solvable
# note can need a long think first (duet: gaia_50f58759 needed >6k output; a small cap
# regresses such notes to a marker). RETRIES are capped cheaply: a retry after a
# think-spiral deterministically re-spirals at temperature 0, so paying the full
# remaining room again is pure waste.
WRAPUP_RETRY_CAP = int(os.environ.get("CHAINLOSS_WRAPUP_RETRY_CAP", "4000"))


def continue_agent(result, user_prompt, client, model, *, meter=None,
                   slice_budget=None, usd_budget=None) -> AgentResult:
    """Append one user message to a finished agent's transcript and get its terminal
    text. The wrap-up seam: the shift, holding its full working memory, is asked for a
    hand-off note, or the last shift is forced to commit. This is a terminal artifact
    (reflection / decision), NOT more investigation, so no tools are offered.

    `slice_budget` + `meter`: each attempt's max_tokens is the slice's remaining
    completion tokens, floored at WRAPUP_FLOOR_TOKENS so an artifact can always at
    least be attempted (the bounded overrun the caller logs).

    Robustness (two coupled failure modes on Qwen3.6, both inherited from duet):
      1. A shift cut off mid-work often tries to keep investigating — it emits a
         <tool_call>, which the proxy parses into tool_calls even though we sent no
         schemas, leaving the visible content empty.
      2. Asked to REFLECT over its raw tool dumps, the model re-analyzes all of them
         and spirals past the token cap inside <think>; the proxy returns its
         truncation sentinel — a NON-empty string that must not be mistaken for a note.
    We first `_compact_for_wrapup` (stub old tool dumps -> no spiral), then loop: any
    reply that is empty, the sentinel, or a truncated ('length') generation is NOT
    honored — we record it text-only and re-ask, firmly, for plain prose (up to
    WRAPUP_MAX_TRIES). If it never writes usable text, `.final` is '' and finish
    carries the last failure so the caller substitutes a marker."""
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
        cap = None
        if slice_budget is not None and meter is not None:
            cap = max(WRAPUP_FLOOR_TOKENS, slice_budget - meter.spent)
        if attempt > 0:
            cap = min(cap, WRAPUP_RETRY_CAP) if cap else WRAPUP_RETRY_CAP
        msg, fr, _ = _call(client, model, wire, None, usd_budget,
                           meters=(meter,) if meter is not None else (), cap=cap)
        n_extra += 1
        if msg is None:
            finish = "ctx_overflow"
            break
        # text-only: any tool_calls the model emitted are dropped (unhonored), so message
        # ordering stays valid across retries (no dangling tool_calls awaiting a response).
        a = _assistant_dict(msg, drop_tool_calls=True)
        record.append(a); wire.append(a)
        finish = "length" if fr == "length" else "stop"
        # Usable only if it is real text AND cleanly terminated. A 'length' generation is
        # a partial/spiralled note; retry for a clean short one rather than crossing a stub.
        if fr != "length" and _usable_text(msg.content):
            final = (msg.content or "").strip()
            break
        if attempt < WRAPUP_MAX_TRIES - 1:      # empty / sentinel / truncated -> re-ask firmly
            nudge = {"role": "user", "content": prompts.WRAPUP_NUDGE}
            record.append(nudge); wire.append(nudge)
    return AgentResult(role=result.role, final=final, n_steps=result.n_steps + n_extra,
                       n_tool_calls=result.n_tool_calls, transcript=record, finish=finish)
