"""A scriptable stand-in for llm.chat, dispatching on the call's tag.

FakeLLM(script) where script maps tag -> list of responses; each response is a
message dict (use `mk`/`mk_tool`) or a callable(messages, tools) -> message.
When a tag's list runs out, the last entry repeats. Every call is recorded in
.calls as (tag, messages, tools) for hygiene assertions.
"""


def mk(content):
    return {"role": "assistant", "content": content, "_usage": {}, "_finish": "stop"}


def mk_tool(name, arguments_json, call_id="c1"):
    return {"role": "assistant", "content": None, "_usage": {}, "_finish": "tool_calls",
            "tool_calls": [{"id": call_id, "type": "function",
                            "function": {"name": name, "arguments": arguments_json}}]}


class FakeLLM:
    def __init__(self, script):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = []

    def __call__(self, messages, tools=None, max_tokens=None, tag="", retries=4):
        self.calls.append((tag, [dict(m) for m in messages], tools))
        entries = self.script.get(tag)
        assert entries, f"FakeLLM: no script for tag {tag!r}"
        entry = entries.pop(0) if len(entries) > 1 else entries[0]
        msg = entry(messages, tools) if callable(entry) else entry
        return dict(msg)

    def calls_for(self, tag):
        return [c for c in self.calls if c[0] == tag]
