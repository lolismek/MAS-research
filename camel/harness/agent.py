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
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=specs,
            temperature=TEMPERATURE, stream=False)
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
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
    else:
        # Hit the backstop; use the last assistant text we have, if any.
        final = next((m["content"] for m in reversed(messages)
                      if m["role"] == "assistant" and m.get("content")), "")

    result = AgentResult(role=role, final=(final or "").strip(),
                         n_steps=n_steps, n_tool_calls=n_tools, transcript=messages)
    addon.on_turn_end(role, result)
    return result
