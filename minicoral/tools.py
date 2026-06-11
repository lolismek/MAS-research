"""ToolExecutor: the agent's 4-tool surface (bash/read_file/write_file/edit_file).

- Path confinement by *resolved* path: allowed roots are the agent worktree and
  .coral/public/; everything else (private/, sidecars/, .. escapes, symlink
  escapes) is denied with an error-as-tool-result.
- bash interception: `coral ...` is parsed (shlex) and dispatched to the
  in-process CoralCLI; `git ...` is rejected with the paper's ground rule.
- Note hooks (latent seam #2): write_file/edit_file under notes/ fire
  transport.on_note_write(path, last_gen, agent_id); read_file under notes/
  fires on_note_read (payload attached to the ToolResult). After every bash
  command an mtime scan of notes/ catches shell-side note writes
  (payload-less on_note_write).
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .engine import GenResult, InjectionPayload

GROUND_RULE_GIT = (
    "Never run git commands directly. CORAL owns git --- use coral "
    "eval/checkout/revert/diff instead."
)


class CoralUsageError(Exception):
    """Raised by CoralCLI for bad usage; rendered as an error tool result."""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": (
                "Run a shell command in your worktree. Use this for `coral ...` "
                "commands and for inspecting files (ls, etc). Long output is truncated."
            ),
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "shell command"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file and return its contents.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "file path (relative to your worktree)"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Replace an exact occurrence of old_string in the file with "
                "new_string. old_string must appear exactly once."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
]

TOOL_NAMES = {t["function"]["name"] for t in TOOL_SCHEMAS}


@dataclass
class ToolResult:
    tool_call_id: str
    name: str
    content: str
    is_error: bool = False
    injection: InjectionPayload | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class CoralDispatch(Protocol):
    """In-process `coral` CLI surface (CoralCLI in coral_cli.py)."""

    async def dispatch(self, argv: list[str]) -> str: ...


def truncate_output(text: str, max_chars: int) -> str:
    """Head+tail truncation with an explicit marker."""
    if len(text) <= max_chars:
        return text
    head = max_chars * 2 // 3
    tail = max_chars - head
    omitted = len(text) - head - tail
    return f"{text[:head]}\n... [{omitted} chars truncated] ...\n{text[-tail:]}"


class ToolExecutor:
    def __init__(
        self,
        worktree: Path,
        public_dir: Path,
        coral: CoralDispatch | None = None,
        transport: Any = None,  # NoteTransport (transport.py); None -> no hooks
        agent_id: str = "agent-1",
        tool_output_max_chars: int = 2000,
        read_max_chars: int = 20000,
        bash_timeout: float = 120.0,
    ):
        self.worktree = worktree.resolve()
        self.public_dir = public_dir.resolve()
        self.notes_dir = self.public_dir / "notes"
        self.coral = coral
        self.transport = transport
        self.agent_id = agent_id
        self.tool_output_max_chars = tool_output_max_chars
        self.read_max_chars = read_max_chars
        self.bash_timeout = bash_timeout
        self.last_gen: GenResult | None = None  # set by the agent loop each turn

    # -- confinement --------------------------------------------------------

    def _resolve(self, path_str: str, for_write: bool = False) -> Path:
        """Resolve a path and enforce confinement. Raises PermissionError."""
        p = Path(path_str)
        if not p.is_absolute():
            p = self.worktree / p
        resolved = p.resolve()
        coral_root = self.public_dir.parent  # .coral/
        for denied, label in (
            (coral_root / "private", ".coral/private is off-limits"),
            (coral_root / "sidecars", ".coral/sidecars is off-limits"),
        ):
            if resolved == denied or resolved.is_relative_to(denied):
                raise PermissionError(f"access denied: {label}")
        if resolved.is_relative_to(self.worktree):
            # Worktree paths may still escape through a symlink the agent made;
            # resolve() above already followed it, so this branch is safe.
            return resolved
        if resolved.is_relative_to(self.public_dir):
            return resolved
        raise PermissionError(
            f"access denied: {path_str} is outside your worktree and .coral/public"
        )

    def _is_note(self, resolved: Path) -> bool:
        return resolved.is_relative_to(self.notes_dir)

    # -- dispatch ------------------------------------------------------------

    async def execute(self, call) -> ToolResult:
        """Execute a ToolCall; all failures come back as error tool results."""
        handler = {
            "bash": self._bash,
            "read_file": self._read_file,
            "write_file": self._write_file,
            "edit_file": self._edit_file,
        }.get(call.name)
        if handler is None:
            return ToolResult(
                tool_call_id=call.id, name=call.name,
                content=f"unknown tool {call.name!r}; available: bash, read_file, write_file, edit_file",
                is_error=True,
            )
        try:
            return await handler(call)
        except PermissionError as e:
            return ToolResult(tool_call_id=call.id, name=call.name, content=str(e), is_error=True)
        except (TypeError, KeyError):
            schema = next(t for t in TOOL_SCHEMAS if t["function"]["name"] == call.name)
            required = schema["function"]["parameters"]["required"]
            return ToolResult(
                tool_call_id=call.id, name=call.name,
                content=(f"bad arguments for {call.name}: got {sorted(call.arguments)}, "
                         f"required {required}"),
                is_error=True,
            )

    # -- tools ----------------------------------------------------------------

    async def _bash(self, call) -> ToolResult:
        command = call.arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            return ToolResult(tool_call_id=call.id, name="bash",
                              content="bash requires a 'command' string", is_error=True)
        stripped = command.strip()

        if stripped.startswith("git ") or stripped == "git":
            return ToolResult(tool_call_id=call.id, name="bash",
                              content=GROUND_RULE_GIT, is_error=True)

        if stripped.startswith("coral ") or stripped == "coral":
            if self.coral is None:
                return ToolResult(tool_call_id=call.id, name="bash",
                                  content="coral CLI not available", is_error=True)
            try:
                argv = shlex.split(stripped)[1:]
            except ValueError as e:
                return ToolResult(tool_call_id=call.id, name="bash",
                                  content=f"could not parse coral command: {e}", is_error=True)
            try:
                out = await self.coral.dispatch(argv)
                return ToolResult(tool_call_id=call.id, name="bash", content=out,
                                  meta={"coral": argv})
            except CoralUsageError as e:
                return ToolResult(tool_call_id=call.id, name="bash", content=str(e), is_error=True)

        before = self._notes_mtimes()
        try:
            proc = subprocess.run(
                stripped, shell=True, cwd=self.worktree,
                capture_output=True, text=True, timeout=self.bash_timeout,
                env=self._safe_env(),
            )
            out = proc.stdout + (("\n" + proc.stderr) if proc.stderr else "")
            if proc.returncode != 0:
                out += f"\n[exit code {proc.returncode}]"
            result = ToolResult(
                tool_call_id=call.id, name="bash",
                content=truncate_output(out.strip() or "(no output)", self.tool_output_max_chars),
                is_error=proc.returncode != 0,
            )
        except subprocess.TimeoutExpired:
            result = ToolResult(
                tool_call_id=call.id, name="bash",
                content=f"command timed out after {self.bash_timeout:.0f}s", is_error=True,
            )
        self._notes_mtime_fallback(before)
        return result

    async def _read_file(self, call) -> ToolResult:
        resolved = self._resolve(call.arguments["path"])
        if not resolved.is_file():
            return ToolResult(tool_call_id=call.id, name="read_file",
                              content=f"no such file: {call.arguments['path']}", is_error=True)
        content = resolved.read_text(errors="replace")
        injection = None
        if self.transport is not None and self._is_note(resolved):
            injection = self.transport.on_note_read(resolved, self.agent_id)
        return ToolResult(
            tool_call_id=call.id, name="read_file",
            content=truncate_output(content, self.read_max_chars),
            injection=injection,
        )

    async def _write_file(self, call) -> ToolResult:
        resolved = self._resolve(call.arguments["path"], for_write=True)
        content = call.arguments["content"]
        if not isinstance(content, str):
            return ToolResult(tool_call_id=call.id, name="write_file",
                              content="'content' must be a string", is_error=True)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content)
        self._note_write_hook(resolved)
        return ToolResult(tool_call_id=call.id, name="write_file",
                          content=f"wrote {len(content)} chars to {call.arguments['path']}")

    async def _edit_file(self, call) -> ToolResult:
        resolved = self._resolve(call.arguments["path"], for_write=True)
        old, new = call.arguments["old_string"], call.arguments["new_string"]
        if not resolved.is_file():
            return ToolResult(tool_call_id=call.id, name="edit_file",
                              content=f"no such file: {call.arguments['path']}", is_error=True)
        text = resolved.read_text(errors="replace")
        n = text.count(old)
        if n == 0:
            return ToolResult(tool_call_id=call.id, name="edit_file",
                              content="old_string not found in file", is_error=True)
        if n > 1:
            return ToolResult(tool_call_id=call.id, name="edit_file",
                              content=f"old_string occurs {n} times; it must be unique",
                              is_error=True)
        resolved.write_text(text.replace(old, new, 1))
        self._note_write_hook(resolved)
        return ToolResult(tool_call_id=call.id, name="edit_file",
                          content=f"edited {call.arguments['path']}")

    # -- note hooks (latent seam #2) -------------------------------------------

    def _note_write_hook(self, resolved: Path) -> None:
        if self.transport is not None and self._is_note(resolved):
            self.transport.on_note_write(resolved, self.last_gen, self.agent_id)

    def _notes_mtimes(self) -> dict[Path, float]:
        if self.transport is None or not self.notes_dir.is_dir():
            return {}
        return {p: p.stat().st_mtime for p in self.notes_dir.rglob("*") if p.is_file()}

    def _notes_mtime_fallback(self, before: dict[Path, float]) -> None:
        if self.transport is None or not self.notes_dir.is_dir():
            return
        for p in self.notes_dir.rglob("*"):
            if p.is_file() and p.stat().st_mtime != before.get(p):
                self.transport.on_note_write(p, None, self.agent_id)

    def _safe_env(self) -> dict[str, str]:
        import os

        sensitive = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
        return {k: v for k, v in os.environ.items()
                if not any(s in k.upper() for s in sensitive)}
