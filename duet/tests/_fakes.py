"""Shared scripted fake OpenAI client for offline tests — NO LLM, NO network.
Same shape as the inline fakes in test_relay_offline.py (kept there untouched);
new test files import from here."""
import json


_TC_ID = [0]


class _Fn:
    def __init__(self, name, args): self.name, self.arguments = name, args


class _TC:
    def __init__(self, name, args):
        _TC_ID[0] += 1
        self.id, self.type, self.function = f"tc{_TC_ID[0]}", "function", _Fn(name, args)


class _Msg:
    def __init__(self, content, tool_calls, reasoning=None):
        self.content, self.tool_calls = content, tool_calls
        self.reasoning_content = reasoning


class _Choice:
    def __init__(self, msg, fr): self.message, self.finish_reason = msg, fr


class _Usage:
    prompt_tokens, completion_tokens = 100, 50


class _Resp:
    def __init__(self, msg, fr): self.choices, self.usage = [_Choice(msg, fr)], _Usage()


def tool_turn(*calls, reasoning=None):
    """calls: (name, args_dict) pairs -> one assistant turn requesting those tools."""
    return _Resp(_Msg(None, [_TC(n, json.dumps(a)) for n, a in calls], reasoning), "tool_calls")


def text_turn(content, finish="stop", reasoning=None):
    return _Resp(_Msg(content, None, reasoning), finish)


class _Completions:
    def __init__(self, outer): self.outer = outer

    def create(self, **kw):
        self.outer.calls.append(kw)
        assert self.outer.script, "fake client ran out of scripted turns"
        return self.outer.script.pop(0)


class _Chat:
    def __init__(self, outer): self.completions = _Completions(outer)


class FakeClient:
    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.chat = _Chat(self)
