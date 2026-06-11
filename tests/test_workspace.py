"""M2 gate: per-run workspace layout, worktrees, symlinks, gitignore guard."""

import subprocess

import pytest

from minicoral.config import load_config
from minicoral.workspace import build_workspace


@pytest.fixture
def ws(task_yaml, tmp_path):
    cfg = load_config(task_yaml)
    cfg.run.results_dir = str(tmp_path / "results")
    cfg.agents.count = 2
    return build_workspace(cfg, run_ts="testrun"), cfg


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def test_layout(ws):
    w, cfg = ws
    for sub in ("attempts", "notes", "skills", "heartbeat"):
        assert (w.public_dir / sub).is_dir()
    assert (w.public_dir / "eval_count").read_text() == "0"
    assert w.grader_path.is_file()
    assert w.sidecars_dir.is_dir()
    assert (w.run_dir / "config.resolved.yaml").is_file()
    assert (w.repo_dir / "initial_program.py").is_file()


def test_worktrees_and_branches(ws):
    w, cfg = ws
    assert w.agent_ids() == ["agent-1", "agent-2"]
    for agent_id in w.agent_ids():
        wt = w.worktree(agent_id)
        assert git(wt, "branch", "--show-current") == agent_id
        assert (wt / "initial_program.py").is_file()


def test_symlink_resolves_to_shared(ws):
    w, _ = ws
    link = w.worktree("agent-1") / ".coral" / "public"
    assert link.is_symlink()
    assert link.resolve() == w.public_dir.resolve()
    # cross-agent visibility through the symlink
    (w.public_dir / "notes" / "x.md").write_text("hello")
    assert (w.worktree("agent-2") / ".coral" / "public" / "notes" / "x.md").read_text() == "hello"


def test_coral_md_rendered(ws):
    w, cfg = ws
    text = (w.worktree("agent-2") / "CORAL.md").read_text()
    assert "You are agent-2." in text
    assert cfg.task.name in text
    assert "higher is better" in text
    assert "## Runtime Tools" in text
    assert "one of several agents" in text  # multi-agent template at count=2


def test_gitignore_guard(ws):
    w, _ = ws
    wt = w.worktree("agent-1")
    # CORAL.md and the .coral symlink dir must be invisible to git
    assert git(wt, "status", "--porcelain") == ""
    (wt / "new_code.py").write_text("x = 1")
    status = git(wt, "status", "--porcelain")
    assert "new_code.py" in status and ".coral" not in status and "CORAL.md" not in status


def test_single_agent_gets_single_template(task_yaml, tmp_path):
    cfg = load_config(task_yaml)
    cfg.run.results_dir = str(tmp_path / "results")
    cfg.agents.count = 1
    w = build_workspace(cfg, run_ts="solo")
    text = (w.worktree("agent-1") / "CORAL.md").read_text()
    assert "never stop until you reach / beat the best score" in text


def test_existing_run_dir_rejected(ws, task_yaml):
    _, cfg = ws
    with pytest.raises(FileExistsError):
        build_workspace(cfg, run_ts="testrun")
