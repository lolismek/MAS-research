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
from dataclasses import dataclass, field

from tools import tool_specs, run_tool

MAX_INNER_STEPS = 30   # runaway backstop, NOT a budget — most agents stop far sooner
TEMPERATURE = 0.0
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


@dataclass
class AgentResult:
    role: str
    final: str                       # the agent's last text (its published output)
    n_steps: int = 0                 # model calls in the inner loop
    n_tool_calls: int = 0
    transcript: list = field(default_factory=list)   # full message list incl. tool I/O


def run_agent(role, system_prompt, task_messages, tool_names, client, model,
              addon, max_inner_steps=MAX_INNER_STEPS) -> AgentResult:
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
    for _ in range(max_inner_steps):
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, tools=specs,
                temperature=TEMPERATURE, stream=False)
        except Exception as e:
            if not _is_context_overflow(e):
                raise
            # Tool outputs accumulated past the window: compact history, retry once,
            # else stop the loop and publish the best text we already have.
            _compact_tool_history(messages)
            try:
                resp = client.chat.completions.create(
                    model=model, messages=messages, tools=specs,
                    temperature=TEMPERATURE, stream=False)
            except Exception:
                final = next((m["content"] for m in reversed(messages)
                              if m["role"] == "assistant" and m.get("content")), "")
                break
        n_steps += 1
        msg = resp.choices[0].message
        calls = msg.tool_calls or []

        # Record the assistant turn (verbatim, so a later call sees its own tool_calls).
        a = {"role": "assistant", "content": msg.content}
        if calls:
            a["tool_calls"] = [{"id": tc.id, "type": "function",
                                "function": {"name": tc.function.name,
                                             "arguments": tc.function.arguments}}
                               for tc in calls]
        messages.append(a)

        if not calls:
            final = msg.content or ""
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
                         n_steps=n_steps, n_tool_calls=n_tools, transcript=messages)
    addon.on_turn_end(role, result)
    return result
