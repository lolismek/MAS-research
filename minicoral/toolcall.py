"""Normalize model tool-call output -> ToolCall.

Two sources, one shape:
- Qwen3 text output containing <tool_call>{"name": ..., "arguments": {...}}</tool_call>
  blocks (optionally preceded by a <think>...</think> block to strip).
- OpenAI-compatible native tool calls (message.tool_calls with JSON-string args).

Malformed calls are not dropped silently: they come back as ParseError entries
so the agent loop can feed the error text back to the model as a tool result.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    id: str = field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")


@dataclass
class ParseError:
    raw: str
    error: str


@dataclass
class ParsedOutput:
    text: str  # assistant-visible text with <think> and <tool_call> blocks removed
    thinking: str  # stripped <think> content (kept for the trajectory log)
    tool_calls: list[ToolCall]
    errors: list[ParseError]


_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)
_TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
# Unclosed block at the end of output (generation stopped mid-call).
_OPEN_TOOL_CALL_RE = re.compile(r"<tool_call>(?!.*</tool_call>)(.*)$", re.DOTALL)


def _normalize_one(payload: Any, raw: str) -> ToolCall | ParseError:
    if not isinstance(payload, dict):
        return ParseError(raw=raw, error="tool call JSON is not an object")
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        return ParseError(raw=raw, error="tool call has no 'name'")
    args = payload.get("arguments", {})
    if isinstance(args, str):
        # Some models double-encode arguments.
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return ParseError(raw=raw, error="'arguments' is a string but not valid JSON")
    if not isinstance(args, dict):
        return ParseError(raw=raw, error="'arguments' is not an object")
    return ToolCall(name=name, arguments=args)


def parse_qwen3(output: str) -> ParsedOutput:
    """Parse raw Qwen3 generation text into clean text + tool calls."""
    thinking = "\n".join(m.strip() for m in _THINK_RE.findall(output))
    rest = _THINK_RE.sub("", output)

    tool_calls: list[ToolCall] = []
    errors: list[ParseError] = []
    for raw in _TOOL_CALL_RE.findall(rest):
        raw = raw.strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            errors.append(ParseError(raw=raw, error=f"invalid JSON in <tool_call>: {e}"))
            continue
        result = _normalize_one(payload, raw)
        (tool_calls if isinstance(result, ToolCall) else errors).append(result)

    rest_no_calls = _TOOL_CALL_RE.sub("", rest)
    m = _OPEN_TOOL_CALL_RE.search(rest_no_calls)
    if m:
        errors.append(ParseError(raw=m.group(1).strip(),
                                 error="unterminated <tool_call> block (output truncated?)"))
        rest_no_calls = rest_no_calls[: m.start()]

    return ParsedOutput(
        text=rest_no_calls.strip(),
        thinking=thinking,
        tool_calls=tool_calls,
        errors=errors,
    )


def parse_api_tool_calls(raw_tool_calls: list[Any] | None) -> tuple[list[ToolCall], list[ParseError]]:
    """Normalize OpenAI-compatible message.tool_calls (objects or dicts)."""
    tool_calls: list[ToolCall] = []
    errors: list[ParseError] = []
    for tc in raw_tool_calls or []:
        if isinstance(tc, dict):
            fn = tc.get("function") or {}
            name, args_raw = fn.get("name"), fn.get("arguments")
            call_id = tc.get("id")
        else:  # openai SDK object
            name, args_raw = tc.function.name, tc.function.arguments
            call_id = tc.id
        try:
            args = json.loads(args_raw) if args_raw else {}
        except json.JSONDecodeError as e:
            errors.append(ParseError(raw=str(args_raw), error=f"invalid JSON arguments: {e}"))
            continue
        result = _normalize_one({"name": name, "arguments": args}, str(args_raw))
        if isinstance(result, ToolCall) and call_id:
            result.id = call_id
        (tool_calls if isinstance(result, ToolCall) else errors).append(result)
    return tool_calls, errors
