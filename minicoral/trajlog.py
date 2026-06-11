"""Append-only trajectory logging.

Per-agent: logs/<agent_id>.traj.jsonl --- every event the agent loop produces,
with token counts and gen params. The invariant: the log must be sufficient to
reconstruct any context the model ever saw (session_start + assistant +
tool_result + compaction events carry full message content).

Run-level: run.events.jsonl --- orchestration events (agent starts/stops,
restarts, termination).

Event types: session_start, assistant, tool_call, tool_result, eval,
heartbeat, compaction, note_write, note_read, agent_restart, error.
"""

from __future__ import annotations

import json
from pathlib import Path

from .hub import utc_now_iso

EVENT_TYPES = {
    "session_start", "assistant", "tool_call", "tool_result", "eval",
    "heartbeat", "compaction", "note_write", "note_read", "agent_restart",
    "error",
    # run.events.jsonl (orchestrator-level)
    "run_start", "run_stop", "agent_start", "agent_stop",
}


class TrajLogger:
    def __init__(self, path: Path, agent_id: str | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.agent_id = agent_id

    def log(self, event_type: str, **fields) -> None:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown trajectory event type {event_type!r}")
        record = {"ts": utc_now_iso(), "type": event_type}
        if self.agent_id is not None:
            record["agent_id"] = self.agent_id
        record.update(fields)
        with self.path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def events(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line]
