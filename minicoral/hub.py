"""Shared persistent memory CRUD: attempts, notes, skills, eval_count,
checkpoints (paper C.4 + attempt schema from C.2/C.4).

The Hub wraps .coral/public/. Checkpoints are git snapshots of the whole
public dir taken at eval time (a bare-ish repo living in
.coral/public/.git, created on first use); the resulting commit hash is the
attempt's checkpoint_hash.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

VALID_STATUSES = ("improved", "baseline", "regressed", "crashed", "timeout")


@dataclass
class Attempt:
    commit_hash: str
    agent_id: str
    title: str  # from `coral eval -m`
    score: float | None
    status: str  # improved|baseline|regressed|crashed|timeout (vs own best)
    parent_hash: str | None
    timestamp: str  # ISO8601
    feedback: str
    checkpoint_hash: str | None = None

    def __post_init__(self):
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid status {self.status!r}")

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "Attempt":
        return cls(**json.loads(text))


def utc_now_iso() -> str:
    # microsecond precision: attempt ordering relies on timestamp sort
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class Hub:
    def __init__(self, public_dir: Path, direction: str = "maximize"):
        self.public_dir = Path(public_dir)
        self.direction = direction
        self.attempts_dir = self.public_dir / "attempts"
        self.notes_dir = self.public_dir / "notes"
        self.skills_dir = self.public_dir / "skills"
        self.eval_count_path = self.public_dir / "eval_count"

    # -- attempts -------------------------------------------------------------

    def record_attempt(self, attempt: Attempt) -> Path:
        path = self.attempts_dir / f"{attempt.commit_hash}.json"
        path.write_text(attempt.to_json())
        return path

    def attempts(self) -> list[Attempt]:
        out = []
        for p in sorted(self.attempts_dir.glob("*.json")):
            try:
                out.append(Attempt.from_json(p.read_text()))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        out.sort(key=lambda a: a.timestamp)
        return out

    def attempt(self, hash_prefix: str) -> Attempt | None:
        matches = list(self.attempts_dir.glob(f"{hash_prefix}*.json"))
        if len(matches) != 1:
            return None
        return Attempt.from_json(matches[0].read_text())

    def _better(self, a: float, b: float) -> bool:
        return a > b if self.direction == "maximize" else a < b

    def best_score(self, agent_id: str | None = None) -> float | None:
        scores = [
            a.score for a in self.attempts()
            if a.score is not None and (agent_id is None or a.agent_id == agent_id)
        ]
        if not scores:
            return None
        return max(scores) if self.direction == "maximize" else min(scores)

    def best_attempt(self) -> Attempt | None:
        scored = [a for a in self.attempts() if a.score is not None]
        if not scored:
            return None
        return (max if self.direction == "maximize" else min)(scored, key=lambda a: a.score)

    def classify(self, score: float | None, own_best: float | None,
                 *, timed_out: bool = False, crashed: bool = False) -> str:
        """Status vs the agent's *own* previous best, direction-aware (C.2 step 4)."""
        if timed_out:
            return "timeout"
        if crashed or score is None:
            return "crashed"
        if own_best is None:
            return "baseline"
        if self._better(score, own_best):
            return "improved"
        if score == own_best:
            return "baseline"
        return "regressed"

    # -- global eval counter (C.2 step 7) --------------------------------------

    def eval_count(self) -> int:
        try:
            return int(self.eval_count_path.read_text().strip() or 0)
        except (FileNotFoundError, ValueError):
            return 0

    def increment_eval_count(self) -> int:
        n = self.eval_count() + 1
        self.eval_count_path.write_text(str(n))
        return n

    # -- checkpoints (C.2 step 6) -----------------------------------------------

    def checkpoint(self) -> str:
        """Snapshot .coral/public into its internal git repo; return commit hash."""
        if not (self.public_dir / ".git").exists():
            self._git("init", "-q", "-b", "main")
            self._git("config", "user.email", "minicoral@local")
            self._git("config", "user.name", "minicoral-hub")
        self._git("add", "-A")
        self._git("commit", "-q", "--allow-empty", "-m", "checkpoint")
        return self._git("rev-parse", "HEAD")

    def _git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(self.public_dir), *args],
            capture_output=True, text=True, check=True,
        )
        return proc.stdout.strip()

    # -- notes / skills ----------------------------------------------------------

    def list_notes(self) -> list[str]:
        if not self.notes_dir.is_dir():
            return []
        return sorted(
            str(p.relative_to(self.notes_dir))
            for p in self.notes_dir.rglob("*") if p.is_file() and p.suffix == ".md"
        )

    def search_notes(self, query: str) -> list[str]:
        q = query.lower()
        hits = []
        for rel in self.list_notes():
            text = (self.notes_dir / rel).read_text(errors="replace")
            if q in rel.lower() or q in text.lower():
                hits.append(rel)
        return hits

    def read_note(self, rel: str) -> str | None:
        p = (self.notes_dir / rel).resolve()
        if not p.is_relative_to(self.notes_dir.resolve()) or not p.is_file():
            return None
        return p.read_text(errors="replace")

    def list_skills(self) -> list[tuple[str, str]]:
        """[(name, first description-ish line of SKILL.md)]"""
        out = []
        if not self.skills_dir.is_dir():
            return out
        for d in sorted(self.skills_dir.iterdir()):
            skill_md = d / "SKILL.md"
            if not skill_md.is_file():
                continue
            desc = ""
            for line in skill_md.read_text(errors="replace").splitlines():
                if line.startswith("description:"):
                    desc = line.split(":", 1)[1].strip()
                    break
            out.append((d.name, desc))
        return out

    def read_skill(self, name: str) -> str | None:
        p = (self.skills_dir / name / "SKILL.md").resolve()
        if not p.is_relative_to(self.skills_dir.resolve()) or not p.is_file():
            return None
        return p.read_text(errors="replace")
