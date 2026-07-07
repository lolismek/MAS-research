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


def _call(client, model, messages, specs, usd_budget):
    """One model call with lazy context-bounding + a single compact-and-retry on overflow.
    Returns (message, finish_reason, over_budget). On unrecoverable overflow, returns a
    synthetic (None, 'ctx_overflow', over_budget)."""
    _bound_context(messages)
    try:
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=specs, temperature=TEMPERATURE,
            stream=False, max_tokens=_max_tokens_for(messages))
    except Exception as e:
        if not _is_context_overflow(e):
            raise
        _bound_context(messages, trigger_headroom=MODEL_CTX, target_headroom=MODEL_CTX // 2)
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, tools=specs, temperature=TEMPERATURE,
                stream=False, max_tokens=_max_tokens_for(messages))
        except Exception:
            return None, "ctx_overflow", False
    over = usd_budget.charge(getattr(resp, "usage", None)) if usd_budget is not None else False
    return resp.choices[0].message, resp.choices[0].finish_reason, over


def _record_assistant(messages, msg):
    """Append the assistant turn verbatim (so a later call sees its own tool_calls)."""
    a = {"role": "assistant", "content": msg.content}
    if msg.tool_calls:
        a["tool_calls"] = [{"id": tc.id, "type": "function",
                            "function": {"name": tc.function.name,
                                         "arguments": tc.function.arguments}}
                           for tc in msg.tool_calls]
    messages.append(a)


def _sig(tc):
    return (tc.function.name, (tc.function.arguments or "").strip())


def run_agent(role, system_prompt, task_messages, tool_names, client, model,
              addon, tool_budget=None, budget_tool_names=None,
              max_inner_steps=MAX_INNER_STEPS, usd_budget=None, env=None) -> AgentResult:
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
    lookups — PLAN relay mechanic 1). All calls are always metered in `n_tool_calls`."""
    messages = [{"role": "system", "content": system_prompt}] + list(task_messages)
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


def continue_agent(result, user_prompt, client, model, addon, usd_budget=None) -> AgentResult:
    """Append one user message to a finished agent's transcript and get its terminal text.
    The wrap-up seam: the shift, holding its full working memory, is asked for a hand-off
    note (hygiene rule 3 — the request is its own delimited user message injected only now),
    or the last shift is forced to commit. This is a terminal artifact (reflection /
    decision), NOT more investigation, so no tools are offered.

    Robustness: a shift cut off mid-work often tries to keep investigating — it emits a
    <tool_call>, which the proxy parses into tool_calls even though we sent no schemas,
    leaving the visible content empty. We do NOT honor that call (there is no tool at a
    wrap-up): we record the turn text-only and re-ask, firmly, for plain prose (up to
    WRAPUP_MAX_TRIES). If it never writes text, `.final` is '' and the caller substitutes a
    marker (raw reasoning / a blank must never cross an edge — rule 6)."""
    messages = result.transcript
    messages.append({"role": "user", "content": user_prompt})
    n_extra = 0
    final, finish = "", "stop"
    for attempt in range(WRAPUP_MAX_TRIES):
        if usd_budget is not None and usd_budget.exceeded:
            finish = "budget"
            break
        msg, fr, _ = _call(client, model, messages, None, usd_budget)
        n_extra += 1
        if msg is None:
            finish = "ctx_overflow"
            break
        # text-only: any tool_calls the model emitted are dropped (unhonored), so message
        # ordering stays valid across retries (no dangling tool_calls awaiting a response).
        messages.append({"role": "assistant", "content": msg.content or ""})
        finish = "length" if fr == "length" else "stop"
        content = (msg.content or "").strip()
        if content:
            final = content
            break
        if attempt < WRAPUP_MAX_TRIES - 1:      # empty (tool-call-only / think-only) -> re-ask
            messages.append({"role": "user", "content": prompts.WRAPUP_NUDGE})
    out = AgentResult(role=result.role, final=final, n_steps=result.n_steps + n_extra,
                      n_tool_calls=result.n_tool_calls, transcript=messages, finish=finish)
    addon.on_turn_end(result.role, out)
    return out
