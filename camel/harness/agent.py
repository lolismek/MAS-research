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


def _compact_tool_history(messages, cap=1200):
    """Last-ditch when even capped outputs accumulate past the context window:
    hard-shrink every tool message already in history, oldest content first."""
    for m in messages:
        if m.get("role") == "tool":
            m["content"] = _truncate(m.get("content"), cap)


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
    specs = tool_specs(tool_names)

    n_steps = n_tools = 0
    final = ""
    finish = "step_cap"            # overwritten on a clean exit; stays if we run the loop out
    for _ in range(max_inner_steps):
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, tools=specs,
                temperature=TEMPERATURE, stream=False, max_tokens=_max_tokens_for(messages))
        except Exception as e:
            if not _is_context_overflow(e):
                raise
            # Tool outputs accumulated past the window: compact history, retry once,
            # else stop the loop and publish the best text we already have.
            _compact_tool_history(messages)
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
            out = run_tool(tc.function.name, tc.function.arguments)
            n_tools += 1
            cap = FILE_TOOL_CHARS if tc.function.name in _FILE_TOOLS else MAX_TOOL_CHARS
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
