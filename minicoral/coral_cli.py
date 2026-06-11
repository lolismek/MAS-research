"""CoralCLI: the agent-facing `coral` command surface (paper Table 6 subset)
including the exact C.2 eval pipeline.

One instance per agent (knows its worktree + agent_id). Reached in-process via
bash interception in tools.py. Bad usage raises CoralUsageError, which the
tool layer renders as an error tool result.

eval pipeline (C.2):
  1. stage & commit in the worktree (--allow-empty: every eval gets a hash)
  2-3. grade the commit in isolation (git archive -> tmp dir -> GraderRunner
       subprocess with hard timeout); the agent can't symlink at the grader
  4. status vs the agent's own previous best (direction-aware)
  5. record attempt JSON
  6. checkpoint shared state (hash written back into the attempt record)
  7. increment global eval_count
  -> formatted result, plus any triggered heartbeat prompts appended
"""

from __future__ import annotations

import subprocess
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from .grader import GraderRunner
from .hub import Attempt, Hub, utc_now_iso
from .tools import CoralUsageError


class CoralCLI:
    def __init__(
        self,
        agent_id: str,
        worktree: Path,
        hub: Hub,
        grader: GraderRunner,
        heartbeat: Any = None,  # HeartbeatMonitor (M5); None -> no prompts
        on_eval: Any = None,  # optional callback(attempt) for logging
    ):
        self.agent_id = agent_id
        self.worktree = Path(worktree)
        self.hub = hub
        self.grader = grader
        self.heartbeat = heartbeat
        self.on_eval = on_eval

    # -- git helpers (CORAL owns git) -------------------------------------------

    def _git(self, *args: str, check: bool = True) -> str:
        proc = subprocess.run(
            ["git", "-C", str(self.worktree), *args],
            capture_output=True, text=True,
        )
        if check and proc.returncode != 0:
            raise CoralUsageError(f"internal git error: {proc.stderr.strip()[:300]}")
        return proc.stdout.strip()

    def _resolve_hash(self, prefix: str) -> str:
        attempt = self.hub.attempt(prefix)
        if attempt is not None:
            return attempt.commit_hash
        out = subprocess.run(
            ["git", "-C", str(self.worktree), "rev-parse", "--verify", "--quiet",
             f"{prefix}^{{commit}}"],
            capture_output=True, text=True,
        )
        if out.returncode != 0:
            raise CoralUsageError(f"unknown attempt hash: {prefix}")
        return out.stdout.strip()

    # -- dispatch ------------------------------------------------------------------

    async def dispatch(self, argv: list[str]) -> str:
        if not argv:
            raise CoralUsageError(
                "usage: coral <eval|log|show|checkout|diff|revert|notes|skills|heartbeat> ..."
            )
        cmd, *rest = argv
        handlers = {
            "eval": self.cmd_eval,
            "log": self.cmd_log,
            "show": self.cmd_show,
            "checkout": self.cmd_checkout,
            "diff": self.cmd_diff,
            "revert": self.cmd_revert,
            "notes": self.cmd_notes,
            "skills": self.cmd_skills,
            "heartbeat": self.cmd_heartbeat,
        }
        handler = handlers.get(cmd)
        if handler is None:
            raise CoralUsageError(
                f"unknown coral command {cmd!r}; available: {', '.join(sorted(handlers))}"
            )
        result = handler(rest)
        if hasattr(result, "__await__"):
            result = await result
        return result

    # -- eval (C.2) -------------------------------------------------------------------

    async def cmd_eval(self, args: list[str]) -> str:
        if len(args) != 2 or args[0] != "-m" or not args[1].strip():
            raise CoralUsageError('usage: coral eval -m "what you changed and why"')
        title = args[1].strip()

        # 1. stage & commit
        parent = self._git("rev-parse", "--quiet", "--verify", "HEAD", check=False) or None
        self._git("add", "-A")
        self._git("commit", "-q", "--allow-empty", "-m", title)
        commit_hash = self._git("rev-parse", "HEAD")

        # 2-3. grade the committed snapshot in isolation
        own_best_before = self.hub.best_score(self.agent_id)
        with tempfile.TemporaryDirectory(prefix="minicoral-grade-") as tmp:
            code_dir = Path(tmp) / "code"
            code_dir.mkdir()
            self._export_commit(commit_hash, code_dir)
            grade = await self.grader.grade(code_dir)

        # 4. status vs own previous best
        status = self.hub.classify(
            grade.score, own_best_before,
            timed_out=grade.timed_out, crashed=grade.crashed,
        )

        # 5. record attempt
        attempt = Attempt(
            commit_hash=commit_hash,
            agent_id=self.agent_id,
            title=title,
            score=grade.score,
            status=status,
            parent_hash=parent,
            timestamp=utc_now_iso(),
            feedback=grade.feedback,
        )
        self.hub.record_attempt(attempt)

        # 6. checkpoint shared state, then pin the hash into the record
        attempt.checkpoint_hash = self.hub.checkpoint()
        self.hub.record_attempt(attempt)

        # 7. global eval counter
        global_count = self.hub.increment_eval_count()

        if self.on_eval is not None:
            self.on_eval(attempt)

        out = self._format_eval_result(attempt, global_count)

        # heartbeat prompts ride along with the eval result (eval-boundary delivery)
        if self.heartbeat is not None:
            prompts = self.heartbeat.on_eval(self.agent_id, attempt, global_count)
            for p in prompts:
                out += f"\n\n--- HEARTBEAT ---\n{p}"
        return out

    def _export_commit(self, commit_hash: str, dest: Path) -> None:
        proc = subprocess.run(
            ["git", "-C", str(self.worktree), "archive", commit_hash],
            capture_output=True, check=True,
        )
        def neutralize_escapes(member, path):
            # C.7 isolation: links escaping the snapshot are dropped, not followed
            try:
                return tarfile.data_filter(member, path)
            except tarfile.FilterError:
                return None

        with tarfile.open(fileobj=BytesIO(proc.stdout)) as tf:
            tf.extractall(dest, filter=neutralize_escapes)

    def _format_eval_result(self, a: Attempt, global_count: int) -> str:
        own_best = self.hub.best_score(self.agent_id)
        global_best = self.hub.best_score()
        score = "none" if a.score is None else f"{a.score:.6g}"
        fmt = lambda s: "none" if s is None else f"{s:.6g}"
        return (
            f"eval #{global_count} | attempt {a.commit_hash[:8]} | status: {a.status}\n"
            f"score: {score} (your best: {fmt(own_best)}, global best: {fmt(global_best)})\n"
            f"feedback: {a.feedback}"
        )

    # -- query commands -------------------------------------------------------------

    def cmd_log(self, args: list[str]) -> str:
        n, recent, search, agent = 20, False, None, None
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-n":
                i += 1
                if i >= len(args) or not args[i].isdigit():
                    raise CoralUsageError("usage: coral log [-n N] [--recent] [--search kw] [--agent id]")
                n = int(args[i])
            elif arg == "--recent":
                recent = True
            elif arg == "--search":
                i += 1
                if i >= len(args):
                    raise CoralUsageError("--search requires a keyword")
                search = args[i].lower()
            elif arg == "--agent":
                i += 1
                if i >= len(args):
                    raise CoralUsageError("--agent requires an agent id")
                agent = args[i]
            else:
                raise CoralUsageError(f"unknown coral log option: {arg}")
            i += 1

        attempts = self.hub.attempts()
        if agent:
            attempts = [a for a in attempts if a.agent_id == agent]
        if search:
            attempts = [a for a in attempts
                        if search in a.title.lower() or search in a.feedback.lower()]
        if recent:
            attempts = sorted(attempts, key=lambda a: a.timestamp, reverse=True)
        else:  # leaderboard: scored attempts ranked best-first, unscored last
            scored = [a for a in attempts if a.score is not None]
            unscored = [a for a in attempts if a.score is None]
            scored.sort(key=lambda a: a.score, reverse=self.hub.direction == "maximize")
            attempts = scored + unscored
        attempts = attempts[:n]
        if not attempts:
            return "no attempts yet"

        lines = [f"{'score':>12}  {'status':<10} {'agent':<9} {'hash':<9} title"]
        for a in attempts:
            score = "-" if a.score is None else f"{a.score:.6g}"
            lines.append(
                f"{score:>12}  {a.status:<10} {a.agent_id:<9} {a.commit_hash[:8]:<9} "
                f"{a.title[:70]}"
            )
        return "\n".join(lines)

    def cmd_show(self, args: list[str]) -> str:
        show_diff = "--diff" in args
        hashes = [a for a in args if a != "--diff"]
        if len(hashes) != 1:
            raise CoralUsageError("usage: coral show <hash> [--diff]")
        full = self._resolve_hash(hashes[0])
        attempt = self.hub.attempt(full)
        if attempt is None:
            raise CoralUsageError(f"no attempt record for {hashes[0]}")
        score = "none" if attempt.score is None else f"{attempt.score:.6g}"
        out = (
            f"attempt {attempt.commit_hash}\n"
            f"agent:     {attempt.agent_id}\n"
            f"status:    {attempt.status}\n"
            f"score:     {score}\n"
            f"parent:    {attempt.parent_hash or 'none'}\n"
            f"timestamp: {attempt.timestamp}\n"
            f"title:     {attempt.title}\n"
            f"feedback:  {attempt.feedback}"
        )
        if show_diff:
            out += "\n\n" + (self._git("show", "--format=", attempt.commit_hash) or "(empty diff)")
        return out

    # -- workflow commands -------------------------------------------------------------

    def cmd_checkout(self, args: list[str]) -> str:
        if len(args) != 1:
            raise CoralUsageError("usage: coral checkout <hash>")
        full = self._resolve_hash(args[0])
        self._git("reset", "--hard", "-q", full)
        return f"worktree reset to attempt {full[:8]}"

    def cmd_diff(self, args: list[str]) -> str:
        if args:
            raise CoralUsageError("usage: coral diff (shows uncommitted changes)")
        diff = self._git("diff", "HEAD")
        untracked = self._git("ls-files", "--others", "--exclude-standard")
        out = diff or "(no uncommitted changes)"
        if untracked:
            out += "\n\nuntracked files:\n" + untracked
        return out

    def cmd_revert(self, args: list[str]) -> str:
        if args:
            raise CoralUsageError("usage: coral revert (undoes the last commit)")
        head = self._git("rev-parse", "HEAD")
        parent = self._git("rev-parse", "--quiet", "--verify", "HEAD~1", check=False)
        if not parent:
            raise CoralUsageError("nothing to revert: this is the first commit")
        self._git("reset", "--hard", "-q", "HEAD~1")
        return f"reverted last commit {head[:8]}; now at {parent[:8]}"

    # -- knowledge commands -------------------------------------------------------------

    def cmd_notes(self, args: list[str]) -> str:
        if not args:
            notes = self.hub.list_notes()
            return "\n".join(notes) if notes else "no notes yet"
        if args[0] == "read":
            if len(args) != 2:
                raise CoralUsageError("usage: coral notes read <path>")
            text = self.hub.read_note(args[1])
            if text is None:
                raise CoralUsageError(f"no such note: {args[1]}")
            return text
        if args[0] == "--search":
            if len(args) != 2:
                raise CoralUsageError("usage: coral notes --search <keyword>")
            hits = self.hub.search_notes(args[1])
            return "\n".join(hits) if hits else f"no notes matching {args[1]!r}"
        raise CoralUsageError("usage: coral notes [--search <kw>] [read <path>]")

    def cmd_skills(self, args: list[str]) -> str:
        if not args:
            skills = self.hub.list_skills()
            if not skills:
                return "no skills yet"
            return "\n".join(f"{name}: {desc}" if desc else name for name, desc in skills)
        if args[0] == "read":
            if len(args) != 2:
                raise CoralUsageError("usage: coral skills read <name>")
            text = self.hub.read_skill(args[1])
            if text is None:
                raise CoralUsageError(f"no such skill: {args[1]}")
            return text
        raise CoralUsageError("usage: coral skills [read <name>]")

    def cmd_heartbeat(self, args: list[str]) -> str:
        if args:
            raise CoralUsageError("usage: coral heartbeat (view only)")
        if self.heartbeat is None:
            return "no heartbeat configured"
        return self.heartbeat.describe()
