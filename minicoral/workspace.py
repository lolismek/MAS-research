"""Per-run workspace: run dir, seed clone, worktrees+branches, symlinks,
CORAL.md, .gitignore guard (paper C.4 layout + C.6 lifecycle steps 1-3).

results/<task>/<ts>/
|-- .coral/
|   |-- public/{attempts,notes,skills,heartbeat}/ + eval_count
|   |-- private/eval/grader.py          (hidden from agents)
|   `-- sidecars/                        (latent mirror; never symlinked)
|-- repo/                                seed clone (git, branch main)
|-- agents/agent-N/                      worktree (branch agent-N)
|   |-- .coral/public -> ../../../.coral/public
|   `-- CORAL.md
|-- logs/
`-- config.resolved.yaml
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .prompts import render_coral_md

# Worktree guard: shared memory and the instruction file stay out of attempts.
WORKTREE_GITIGNORE = """\
.coral/
CORAL.md
__pycache__/
*.pyc
"""


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout.strip()


@dataclass
class Workspace:
    run_dir: Path
    repo_dir: Path
    agents_dir: Path
    logs_dir: Path
    coral_dir: Path

    @property
    def public_dir(self) -> Path:
        return self.coral_dir / "public"

    @property
    def private_dir(self) -> Path:
        return self.coral_dir / "private"

    @property
    def sidecars_dir(self) -> Path:
        return self.coral_dir / "sidecars"

    @property
    def grader_path(self) -> Path:
        return self.private_dir / "eval" / "grader.py"

    def worktree(self, agent_id: str) -> Path:
        return self.agents_dir / agent_id

    def agent_ids(self) -> list[str]:
        return sorted(p.name for p in self.agents_dir.iterdir() if p.is_dir())

    # shared_dir as agents see it (relative to their worktree, via the symlink)
    AGENT_SHARED_DIR = ".coral/public"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def build_workspace(cfg: Config, run_ts: str | None = None) -> Workspace:
    run_ts = run_ts or time.strftime("%Y%m%d-%H%M%S")
    run_dir = Path(cfg.run.results_dir) / slugify(cfg.task.name) / run_ts
    if run_dir.exists():
        raise FileExistsError(f"run dir already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    ws = Workspace(
        run_dir=run_dir,
        repo_dir=run_dir / "repo",
        agents_dir=run_dir / "agents",
        logs_dir=run_dir / "logs",
        coral_dir=run_dir / ".coral",
    )

    # Shared persistent memory (C.4).
    for sub in ("attempts", "notes", "skills", "heartbeat"):
        (ws.public_dir / sub).mkdir(parents=True)
    (ws.public_dir / "eval_count").write_text("0")
    ws.sidecars_dir.mkdir()
    ws.logs_dir.mkdir()

    # Private grader files, copied at run init and confined away from agents (C.7).
    for rel in cfg.grader.private:
        src = (cfg.task.task_dir / rel).resolve()
        dst = ws.private_dir / rel.rstrip("/")
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    if not ws.grader_path.exists():
        raise FileNotFoundError(f"grader.private must provide eval/grader.py (got {cfg.grader.private})")

    # Seed clone: per-run repository the worktrees branch off (C.6 step 1).
    ws.repo_dir.mkdir()
    shutil.copytree(cfg.task.seed_dir, ws.repo_dir, dirs_exist_ok=True)
    (ws.repo_dir / ".gitignore").write_text(WORKTREE_GITIGNORE)
    _git(ws.repo_dir, "init", "-q", "-b", "main")
    _git(ws.repo_dir, "config", "user.email", "minicoral@local")
    _git(ws.repo_dir, "config", "user.name", "minicoral")
    _git(ws.repo_dir, "add", "-A")
    _git(ws.repo_dir, "commit", "-q", "-m", "seed")

    # Agent worktrees with symlinked shared memory + CORAL.md (C.6 step 3).
    ws.agents_dir.mkdir()
    for n in range(1, cfg.agents.count + 1):
        agent_id = f"agent-{n}"
        worktree = ws.worktree(agent_id)
        _git(ws.repo_dir, "worktree", "add", "-q", str(worktree.resolve()), "-b", agent_id)
        coral_link_dir = worktree / ".coral"
        coral_link_dir.mkdir()
        (coral_link_dir / "public").symlink_to(
            Path("..") / ".." / ".." / ".coral" / "public", target_is_directory=True
        )
        (worktree / "CORAL.md").write_text(
            render_coral_md(
                multi_agent=cfg.agents.count > 1,
                task_name=cfg.task.name,
                task_description=cfg.task.description.strip(),
                score_direction=cfg.grader.score_direction_text,
                shared_dir=Workspace.AGENT_SHARED_DIR,
                agent_id=agent_id,
            )
        )

    cfg.dump_resolved(run_dir / "config.resolved.yaml")
    return ws
