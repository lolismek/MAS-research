"""M1 gate: tool-call normalization on canned model outputs."""

import json

from minicoral.toolcall import parse_api_tool_calls, parse_qwen3


def test_well_formed_single_call():
    out = parse_qwen3(
        'Let me check the file.\n<tool_call>\n'
        '{"name": "read_file", "arguments": {"path": "a.py"}}\n'
        "</tool_call>"
    )
    assert len(out.tool_calls) == 1
    assert out.tool_calls[0].name == "read_file"
    assert out.tool_calls[0].arguments == {"path": "a.py"}
    assert out.text == "Let me check the file."
    assert not out.errors


def test_malformed_json_becomes_error():
    out = parse_qwen3('<tool_call>{"name": "bash", "arguments": {oops}</tool_call>')
    assert not out.tool_calls
    assert len(out.errors) == 1
    assert "invalid JSON" in out.errors[0].error


def test_missing_name_becomes_error():
    out = parse_qwen3('<tool_call>{"arguments": {"path": "x"}}</tool_call>')
    assert not out.tool_calls and len(out.errors) == 1
    assert "name" in out.errors[0].error


def test_multi_call_preserves_order():
    out = parse_qwen3(
        '<tool_call>{"name": "read_file", "arguments": {"path": "a"}}</tool_call>\n'
        '<tool_call>{"name": "bash", "arguments": {"command": "ls"}}</tool_call>'
    )
    assert [c.name for c in out.tool_calls] == ["read_file", "bash"]


def test_thinking_stripped_and_kept():
    out = parse_qwen3(
        "<think>I should look at the seed first.</think>\n"
        'Okay.\n<tool_call>{"name": "bash", "arguments": {"command": "coral log"}}</tool_call>'
    )
    assert out.thinking == "I should look at the seed first."
    assert "<think>" not in out.text and out.text == "Okay."
    assert out.tool_calls[0].arguments["command"] == "coral log"


def test_unterminated_block_reported():
    out = parse_qwen3('<tool_call>{"name": "bash", "argu')
    assert not out.tool_calls
    assert any("unterminated" in e.error for e in out.errors)
    assert "<tool_call>" not in out.text


def test_double_encoded_arguments():
    out = parse_qwen3(
        '<tool_call>{"name": "bash", "arguments": "{\\"command\\": \\"ls\\"}"}</tool_call>'
    )
    assert out.tool_calls[0].arguments == {"command": "ls"}


def test_plain_text_no_calls():
    out = parse_qwen3("Just thinking out loud, no action yet.")
    assert not out.tool_calls and not out.errors
    assert out.text == "Just thinking out loud, no action yet."


def test_api_tool_calls_from_dicts():
    calls, errors = parse_api_tool_calls([
        {"id": "call_1", "function": {"name": "write_file",
                                      "arguments": json.dumps({"path": "n.md", "content": "x"})}},
        {"id": "call_2", "function": {"name": "bash", "arguments": "{bad"}},
    ])
    assert len(calls) == 1 and calls[0].id == "call_1"
    assert calls[0].arguments["path"] == "n.md"
    assert len(errors) == 1 and "invalid JSON" in errors[0].error
