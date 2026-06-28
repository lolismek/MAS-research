"""The one primitive: an agent that runs an internal ReAct loop to completion.

This is the ONLY place an LLM is called. `run_agent` takes a role's system prompt
+ a message list, runs (model -> optional tool calls -> observe -> ...) until the
model stops calling tools or hits MAX_INNER_STEPS, and returns the final text plus
the full transcript. Closed-book tasks (empty tool profile) terminate in one
iteration; tool tasks iterate. Qwen3.6 thinks natively (the proxy strips the
<think> trace), so prompts carry NO chain-of-thought instructions.

The model is reached through the shared Tinker proxy route (/m/<tag>/v1): the
client speaks plain OpenAI chat.completions with model 'gpt-4o' (aliased upstream
to Qwen/Qwen3.6-35B-A3B); the proxy converts Qwen's text tool-calls into
structured tool_calls, so we get a normal OpenAI tool loop here.
"""
import os
from dataclasses import dataclass, field

from tools import tool_specs, run_tool

MAX_INNER_STEPS = 30   # runaway backstop, NOT a budget — most agents stop far sooner
TEMPERATURE = 0.0

# Output-length budget. The proxy otherwise defaults every call to 8192 tokens
# (server.py TINKER_MAX_TOKENS); on a thinking model that whole budget gets spent
# in the reasoning trace, so hard GPQA/MATH replies were truncated mid-derivation
# BEFORE the "FINAL ANSWER:" line — the dominant closed-book failure. We set our own,
# much higher cap, sized ADAPTIVELY so prompt+output never exceeds the model context
# (a growing GAIA tool history shrinks the room, gracefully, instead of a hard 400).
MODEL_CTX = int(os.environ.get("CAMEL_MODEL_CTX", "64000"))
MAX_OUTPUT_TOKENS = int(os.environ.get("CAMEL_MAX_TOKENS", "28000"))
_CTX_MARGIN = 2048

# Proactive context bound (GAIA tool loops): the ReAct loop re-sends the whole growing
# tool history every step, so input creeps toward the 64k wall. We compact LAZILY — only
# once the prompt crosses a high-watermark — by stubbing the OLDEST tool results first,
# down to a low-watermark that still leaves room for the next turn's OUTPUT (the model's
# think trace shares the output budget; starving it just moves the truncation to the
# input side). The gap between the two watermarks is hysteresis: it avoids re-compacting
# on every single call. Headrooms are "tokens to reserve for output" — bigger = more room.
_COMPACT_TRIGGER_HEADROOM = int(os.environ.get("CAMEL_COMPACT_TRIGGER", "8000"))   # act below this
_COMPACT_TARGET_HEADROOM = int(os.environ.get("CAMEL_COMPACT_TARGET", "16000"))    # free down to this
_STUB_PREFIX = "[elided] "


def _est_prompt_tokens(messages):
    """Cheap char/4 estimate of the prompt size (no tiktoken in env) — only used to
    leave output headroom, so a rough over-estimate is the safe direction."""
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


MAX_TOOL_CHARS = 6000   # cap a web/tool result: one big fetched page can exceed Qwen's 64k ctx
# read_file returns the task's OWN attached file — the file IS the task, so don't clip it with
# the web-page cap (that silently drops data rows). read_file self-limits (READ_FILE_MAX_CHARS);
# this larger ceiling just lets its output (incl. its actionable truncation note) through whole.
FILE_TOOL_CHARS = 45000
_FILE_TOOLS = {"read_file"}


def _truncate(s, cap=MAX_TOOL_CHARS):
    s = s or ""
    return s if len(s) <= cap else s[:cap] + f"\n…[truncated {len(s) - cap} chars]"


def _tool_call_index(messages):
    """tool_call_id -> 'name(arg-slice)', so an evicted result leaves a re-fetchable
    pointer: the agent can see what the call was and re-issue it if it still needs it."""
    idx = {}
    for m in messages:
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function") or {}
            idx[tc.get("id")] = f"{fn.get('name', 'tool')}({(fn.get('arguments') or '')[:60]})"
    return idx


def _bound_context(messages, trigger_headroom=_COMPACT_TRIGGER_HEADROOM,
                   target_headroom=_COMPACT_TARGET_HEADROOM):
    """Lazily bound the prompt. No-op until est. prompt crosses the high-watermark
    (MODEL_CTX - trigger_headroom); then replace the OLDEST not-yet-stubbed tool results
    with a one-line re-fetchable stub, oldest-first, until under the low-watermark
    (MODEL_CTX - target_headroom). The most-recent tool result is always kept full."""
    if _est_prompt_tokens(messages) <= MODEL_CTX - trigger_headroom:
        return
    idx = _tool_call_index(messages)
    tool_pos = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    keep_last = tool_pos[-1] if tool_pos else None        # never stub the freshest observation
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
    """Per-task USD spend cap, shared across the pipeline's 4 agents.

    Charged live from each response's usage (resp.usage is populated by the proxy).
    Once `spent` crosses `cap`, `exceeded` latches True; the agent loop breaks and
    the pipeline short-circuits to an honest UNKNOWN rather than thrashing on. A
    falsy cap disables the cap (unlimited)."""

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
    final: str                       # the agent's last text (its published output)
    n_steps: int = 0                 # model calls in the inner loop
    n_tool_calls: int = 0
    transcript: list = field(default_factory=list)   # full message list incl. tool I/O
    finish: str = "stop"             # why the loop ended: stop|length|step_cap|ctx_overflow

    @property
    def truncated(self):
        """True when the agent did NOT cleanly finish — output hit the token cap,
        the step backstop, or context overflowed. Such a reply is unlikely to carry
        a committed answer; the pipeline treats it as no_answer, not a confident miss."""
        return self.finish in ("length", "step_cap", "ctx_overflow")


def run_agent(role, system_prompt, task_messages, tool_names, client, model,
              addon, max_inner_steps=MAX_INNER_STEPS, budget=None) -> AgentResult:
    """Run one agent's internal loop and return its AgentResult.

    `task_messages` is the user-side context (task + upstream agents' outputs).
    `addon.inject_context` may prepend shared state before the loop; for vanilla
    it's a no-op so only the polished upstream output is visible.
    """
    messages = [{"role": "system", "content": system_prompt}] + list(task_messages)
    messages = addon.inject_context(role, messages)
    # The AddOn may add agent-callable write-tools (voyager's add_skill) backed by its
    # per-task state. Merge them into the specs; keep the closed-book `or None` contract
    # (an empty profile stays tool-less for vanilla, which adds nothing).
    base_specs = tool_specs(tool_names) or []
    extra_specs = addon.extra_tool_specs(role)
    addon_tools = {s["function"]["name"] for s in extra_specs}
    specs = (base_specs + extra_specs) or None

    n_steps = n_tools = 0
    final = ""
    finish = "step_cap"            # overwritten on a clean exit; stays if we run the loop out
    for _ in range(max_inner_steps):
        _bound_context(messages)        # proactive: stub oldest tool results if near the wall
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, tools=specs,
                temperature=TEMPERATURE, stream=False, max_tokens=_max_tokens_for(messages))
        except Exception as e:
            if not _is_context_overflow(e):
                raise
            # Proactive bound under-estimated and we hit the wall anyway: compact harder
            # (always act, free half the window), retry once, else stop and publish best text.
            _bound_context(messages, trigger_headroom=MODEL_CTX, target_headroom=MODEL_CTX // 2)
            try:
                resp = client.chat.completions.create(
                    model=model, messages=messages, tools=specs,
                    temperature=TEMPERATURE, stream=False, max_tokens=_max_tokens_for(messages))
            except Exception:
                final = next((m["content"] for m in reversed(messages)
                              if m["role"] == "assistant" and m.get("content")), "")
                finish = "ctx_overflow"
                break
        n_steps += 1
        msg = resp.choices[0].message
        fr = resp.choices[0].finish_reason
        over_budget = budget.charge(getattr(resp, "usage", None)) if budget is not None else False
        calls = msg.tool_calls or []

        # Record the assistant turn (verbatim, so a later call sees its own tool_calls).
        a = {"role": "assistant", "content": msg.content}
        if calls:
            a["tool_calls"] = [{"id": tc.id, "type": "function",
                                "function": {"name": tc.function.name,
                                             "arguments": tc.function.arguments}}
                               for tc in calls]
        messages.append(a)

        if not calls or over_budget:           # done, or out of budget -> stop before more tool calls
            final = msg.content or ""
            # 'length' = the reply was still being written when it hit the token cap,
            # so it likely never reached the 'FINAL ANSWER:' line -> no_answer downstream.
            finish = "length" if fr == "length" else "stop"
            break
        for tc in calls:                       # execute every requested tool, append results
            name = tc.function.name
            out = (addon.run_extra_tool(name, tc.function.arguments)   # addon-owned write-tool
                   if name in addon_tools else run_tool(name, tc.function.arguments))
            n_tools += 1
            cap = FILE_TOOL_CHARS if name in _FILE_TOOLS else MAX_TOOL_CHARS
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": _truncate(out, cap)})
    else:
        # Hit the backstop; use the last assistant text we have, if any.
        final = next((m["content"] for m in reversed(messages)
                      if m["role"] == "assistant" and m.get("content")), "")

    result = AgentResult(role=role, final=(final or "").strip(),
                         n_steps=n_steps, n_tool_calls=n_tools, transcript=messages,
                         finish=finish)
    addon.on_turn_end(role, result)
    return result
