"""Shared 'thinking memory': a per-participant scratchpad board with stable note IDs,
append-by-default / revise-only-when-false semantics, an append-only event log for
history + trace, and a bounded active-notes renderer.

One Board instance is shared by reference across all agents' write-tools, the agents'
model-context wrappers, and the selector manager, within a single scenario.py process.
SelectorGroupChat runs participants sequentially (AssistantAgent is not coroutine-safe,
and the manager selects between turns), so no locking is needed.

Gated entirely behind SHARED_MEMORY=1 in scenario_split.py; when off, none of this is
constructed and the baseline run is byte-identical.
"""
import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from autogen_core.model_context import UnboundedChatCompletionContext
from autogen_core.models import LLMMessage, SystemMessage

# The single guardrail (see plan): bound how much board text can enter context.
MAX_ACTIVE_NOTES_PER_AGENT = 8   # oldest active note is ARCHIVED (kept in history) beyond this
MAX_NOTE_CHARS = 1200            # hard cap on one note so a single write can't blow context


@dataclass
class Note:
    note_id: str                        # stable, e.g. "WebResearcher-3"
    agent: str
    text: str
    active: bool = True                  # False once superseded by a revise or archived by the cap
    created_turn: int = 0
    revised_from: Optional[str] = None   # note_id this revision replaced, if any


class Board:
    """In-process shared scratchpad. Notes are grouped per author, in creation order."""

    def __init__(self) -> None:
        self._notes: Dict[str, List[Note]] = {}
        self._counters: Dict[str, int] = {}
        self.events: List[dict] = []   # append-only log; dumped to board_trace.jsonl
        self._turn = 0                 # coarse logical clock, bumped once per agent turn

    # ---- logical clock (bumped from TeamAwareAssistantAgent._add_messages_to_context) ----
    def mark_turn(self) -> None:
        self._turn += 1

    # ---- mutations (called by write-tools and the selector manager) ----
    def add_note(self, agent: str, text: str) -> Note:
        text = (text or "").strip()[:MAX_NOTE_CHARS]
        self._counters[agent] = self._counters.get(agent, 0) + 1
        nid = f"{agent}-{self._counters[agent]}"
        note = Note(note_id=nid, agent=agent, text=text, created_turn=self._turn)
        self._notes.setdefault(agent, []).append(note)
        self._enforce_cap(agent)
        self._log("add", note)
        return note

    def revise_note(self, agent: str, note_id: str, text: str) -> Optional[Note]:
        """Supersede a now-FALSE note: mark the old one inactive (kept in history) and
        append a new active note recording what it replaced. Returns the new Note, or
        None if note_id is not an active note authored by ``agent``."""
        old = self._find_active(agent, note_id)
        if old is None:
            return None
        old.active = False
        text = (text or "").strip()[:MAX_NOTE_CHARS]
        self._counters[agent] = self._counters.get(agent, 0) + 1
        nid = f"{agent}-{self._counters[agent]}"
        new = Note(note_id=nid, agent=agent, text=text,
                   created_turn=self._turn, revised_from=note_id)
        self._notes[agent].append(new)
        self._enforce_cap(agent)
        self._log("revise", new)
        return new

    # ---- queries ----
    def active_notes(self, agent: Optional[str] = None) -> List[Note]:
        out: List[Note] = []
        for a, notes in self._notes.items():
            if agent is not None and a != agent:
                continue
            out.extend(n for n in notes if n.active)
        return out

    # ---- rendering (read path) ----
    def render(self, for_selector: bool = False) -> str:
        """Bounded, current-versions-only view. Returns '' for an empty board so the
        OFF path and an unused board add ZERO tokens."""
        authors = [a for a in self._notes if any(n.active for n in self._notes[a])]
        if not authors:
            return ""
        if for_selector:
            head = ("SHARED TEAM SCRATCHPAD — each member's current working notes "
                    "(what they believe / tried / are stuck on). Use them to route.")
        else:
            head = ("SHARED TEAM SCRATCHPAD — your teammates' current working notes "
                    "(what each now believes / tried / is stuck on). Read before acting.")
        lines = [f"=== {head} ==="]
        for a in authors:
            lines.append(f"[{a}]")
            for n in self._notes[a]:
                if n.active:
                    tag = f" (revised, replaces {n.revised_from})" if n.revised_from else ""
                    lines.append(f"  - {n.note_id}{tag}: {n.text}")
        lines.append("=== end scratchpad ===")
        return "\n".join(lines)

    # ---- trace ----
    def dump_events_jsonl(self) -> str:
        return "\n".join(json.dumps(e, ensure_ascii=False) for e in self.events)

    # ---- internals ----
    def _enforce_cap(self, agent: str) -> None:
        active = [n for n in self._notes[agent] if n.active]
        excess = len(active) - MAX_ACTIVE_NOTES_PER_AGENT
        if excess <= 0:
            return
        for n in active[:excess]:   # archive the oldest-active; history is preserved
            n.active = False
            self._log("archive", n)

    def _find_active(self, agent: str, note_id: str) -> Optional[Note]:
        for n in self._notes.get(agent, []):
            if n.note_id == note_id and n.active:
                return n
        return None

    def _log(self, op: str, note: Note) -> None:
        self.events.append({
            "op": op, "agent": note.agent, "note_id": note.note_id,
            "text": note.text, "revised_from": note.revised_from,
            "turn": note.created_turn, "wall": round(time.time(), 3),
        })


class BoardInjectingContext(UnboundedChatCompletionContext):
    """An UnboundedChatCompletionContext that prepends a freshly-rendered board block as
    a SystemMessage on EACH get_messages(), and NEVER stores it.

    IMPORTANT — do NOT "optimize" this by calling add_message(): returning the block
    (rather than storing it) keeps it out of the persisted message list, so it is
    recomputed from the live board at every inference (including each tool-loop
    iteration and the reflection step) and does NOT accumulate across turns. Contrast:
    the Memory protocol calls model_context.add_message(SystemMessage(...)) every turn
    (ListMemory.update_context), which DOES accumulate onto the persistent context.
    """

    def __init__(self, board: Board, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._board = board

    async def get_messages(self) -> List[LLMMessage]:
        base = await super().get_messages()
        rendered = self._board.render(for_selector=False)
        if not rendered:
            return base
        return [SystemMessage(content=rendered)] + base
