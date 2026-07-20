"""The one agent primitive (duet's pattern, adapted to a Docker repo env).

run_agent(env, system, user, tool_budget) runs a plain OpenAI tool loop:
model -> tool calls -> observations -> ... until the model stops calling
tools, spends its TOOL-CALL BUDGET, trips the repeated-action guard, or hits
the runaway step cap. Returns the full trajectory (the phase-1 product) plus
final text and usage. This is the ONLY place the LLM is called during
episodes; both phase 1 (agent A, budget k) and phase 2 (agent B, budget m)
use it — only prompts and budgets differ.

Tools are deliberately minimal and identical across phases/arms so protocol
arms differ ONLY in the handoff artifact: bash, read_file, write_file.
"""
import json

from . import llm

MAX_INNER_STEPS = 40      # runaway backstop; the budget stops healthy runs first
REPEAT_LIMIT = 3          # identical (tool,args) in a row -> thrashing; stop
MAX_TOOL_CHARS = 6000     # generic tool-output cap (duet's value)
MAX_FILE_CHARS = 20000    # read_file cap

TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "bash",
        "description": "Run a shell command in the repository container (cwd /workspace/test_repo).",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "The shell command to run."}},
            "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a file (optionally a line range) from the container filesystem.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "start_line": {"type": "integer", "description": "1-based, optional"},
            "end_line": {"type": "integer", "description": "inclusive, optional"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Overwrite (or create) a file in the container with the given content.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"}},
            "required": ["path", "content"]}}},
]


def _run_tool(env, name, args):
    if name == "bash":
        code, out = env.exec(args.get("command", ""), timeout=300)
        out = out or ""
        if len(out) > MAX_TOOL_CHARS:
            out = out[:MAX_TOOL_CHARS // 2] + "\n[... output clipped ...]\n" + out[-MAX_TOOL_CHARS // 2:]
        return f"[exit {code}]\n{out}"
    if name == "read_file":
        content = env.read_file(args.get("path", ""))
        if content is None:
            return "[error: cannot read file]"
        lines = content.split("\n")
        s, e = args.get("start_line"), args.get("end_line")
        if s or e:
            s = max(1, int(s or 1))
            e = min(len(lines), int(e or len(lines)))
            body = "\n".join(f"{i}\t{l}" for i, l in zip(range(s, e + 1), lines[s - 1:e]))
        else:
            body = "\n".join(f"{i}\t{l}" for i, l in enumerate(lines, 1))
        if len(body) > MAX_FILE_CHARS:
            body = body[:MAX_FILE_CHARS] + "\n[... file clipped; request a line range ...]"
        return body
    if name == "write_file":
        ok = env.write_file(args.get("path", ""), args.get("content", ""))
        return "[written]" if ok else "[error: write failed]"
    return f"[error: unknown tool {name}]"


def run_agent(env, system, user, tool_budget, tag="", extra_tools=None):
    """Returns {'events': [...], 'final_text': str|None, 'stop_reason': str,
    'tool_calls_used': int, 'usage': {...}}.

    extra_tools: optional (specs_list, handler) for arm-owned tools (the board
    family's add_belief/revise_belief). Extra-tool calls are FREE — they don't
    consume the environment tool budget, so the board arm's k is comparable to
    plain-family k (recording a belief is not an environment probe)."""
    extra_specs, extra_handler = (extra_tools or ([], None))
    extra_names = {s["function"]["name"] for s in extra_specs}
    specs = TOOL_SPECS + list(extra_specs)
    usage = llm.Usage()
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    events = [{"type": "system", "content": system},
              {"type": "user", "content": user}]
    used = 0
    last_action, repeats = None, 0
    stop_reason, final_text = "model_stopped", None

    for _ in range(MAX_INNER_STEPS):
        msg = llm.chat(messages, tools=specs, tag=tag)
        usage.add(msg.get("_usage", {}))
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []
        events.append({"type": "assistant", "content": content,
                       "tool_calls": [{"name": t["function"]["name"],
                                       "arguments": t["function"]["arguments"]}
                                      for t in tool_calls]})
        assistant_msg = {"role": "assistant", "content": content or None}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        if not tool_calls:
            final_text = content
            stop_reason = "model_stopped"
            break

        budget_hit = False
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            if name in extra_names:
                result = extra_handler(name, args)
                events.append({"type": "extra_tool", "name": name, "arguments": args,
                               "result": result})
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": result})
                continue
            if used >= tool_budget:
                budget_hit = True
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": "[tool budget exhausted]"})
                continue
            action_key = (name, tc["function"]["arguments"])
            repeats = repeats + 1 if action_key == last_action else 1
            last_action = action_key
            used += 1
            result = _run_tool(env, name, args)
            events.append({"type": "tool", "name": name, "arguments": args,
                           "result": result})
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": result})
            if repeats >= REPEAT_LIMIT:
                budget_hit = True
                stop_reason = "repeat_guard"
                break
        if stop_reason == "repeat_guard":
            break
        if budget_hit or used >= tool_budget:
            stop_reason = "budget"
            break
    else:
        stop_reason = "step_cap"

    return {"events": events, "final_text": final_text, "stop_reason": stop_reason,
            "tool_calls_used": used, "usage": usage.as_dict()}
