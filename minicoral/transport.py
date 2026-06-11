"""NoteTransport: latent seam #3.

The transport observes every note write/read (hooks fired by tools.py) and can
attach latent material:
- on_note_write may persist a sidecar (hidden mirror under .coral/sidecars/,
  invisible to agents by construction --- it is never symlinked into worktrees
  and is confinement-denied).
- on_note_read may return an InjectionPayload that the engine applies at
  generation time (HF backend only).

v1 ships TextOnlyTransport (the paper baseline): no capture, no sidecars, no
injection. Probe arms register their transports here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from .engine import GenResult, InjectionPayload


class NoteTransport(Protocol):
    def wants_capture(self) -> bool: ...

    def on_note_write(
        self, note_path: Path, gen: GenResult | None, agent_id: str
    ) -> Path | None: ...

    def on_note_read(self, note_path: Path, agent_id: str) -> InjectionPayload | None: ...


class TextOnlyTransport:
    """Paper baseline: notes are text and nothing else."""

    def wants_capture(self) -> bool:
        return False

    def on_note_write(self, note_path: Path, gen: GenResult | None, agent_id: str) -> Path | None:
        return None

    def on_note_read(self, note_path: Path, agent_id: str) -> InjectionPayload | None:
        return None


_REGISTRY: dict[str, Callable[[Path], NoteTransport]] = {
    "text_only": lambda sidecars_dir: TextOnlyTransport(),
}


def register_transport(kind: str, factory: Callable[[Path], NoteTransport]) -> None:
    _REGISTRY[kind] = factory


def build_transport(kind: str, sidecars_dir: Path) -> NoteTransport:
    if kind not in _REGISTRY:
        raise ValueError(
            f"unknown transport.kind {kind!r}; registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[kind](sidecars_dir)
