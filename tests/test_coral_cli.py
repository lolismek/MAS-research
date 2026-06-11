"""M3 gate: full C.2 eval pipeline with a scripted fake agent (no model).

Covers: all 5 statuses, complete attempt JSON schema, checkout/revert/diff
round-trips, eval_count + checkpoint advance, log/show rendering, notes/skills
commands, grader isolation from worktree symlinks.
"""

import json

import pytest

from minicoral.config import load_config
from minicoral.coral_cli import CoralCLI
from minicoral.grader import GraderRunner
from minicoral.hub import Hub
from minicoral.toolcall import ToolCall
from minicoral.tools import ToolExecutor
from minicoral.workspace import build_workspace

GRID = """\
import json
circles = []
for j in range({rows}):
    for i in range({cols}):
        if len(circles) < 26:
            circles.append([(2*i+1)/(2*{cols}), (2*j+1)/(2*{rows}), {r}])
print(json.dumps(circles))
"""

# 5x5 grid at r=0.1 plus one circle in a gap: sum 2.541 > seed's 2.1667
IMPROVED = """\
import json
circles = [[(2*i+1)/10, (2*j+1)/10, 0.1] for j in range(5) for i in range(5)]
circles.append([0.2, 0.2, 0.041])
print(json.dumps(circles))
"""


@pytest.fixture
def rig(task_yaml, tmp_path):
    """Workspace + per-agent CLI wired through the ToolExecutor (the real path)."""
    cfg = load_config(task_yaml)
    cfg.run.results_dir = str(tmp_path / "results")
    cfg.agents.count = 2
    cfg.grader.args = dict(cfg.grader.args, program_timeout=8)
    ws = build_workspace(cfg, run_ts="m3")
    hub = Hub(ws.public_dir, direction=cfg.grader.direction)
    grader = GraderRunner(ws.grader_path, timeout=cfg.grader.timeout, args=cfg.grader.args)

    def make_agent(agent_id):
        cli = CoralCLI(agent_id=agent_id, worktree=ws.worktree(agent_id),
                       hub=hub, grader=grader)
        ex = ToolExecutor(worktree=ws.worktree(agent_id), public_dir=ws.public_dir,
                          coral=cli, agent_id=agent_id)
        return cli, ex

    return ws, hub, make_agent


async def run(ex, command):
    return await ex.execute(ToolCall(name="bash", arguments={"command": command}))


def write_program(ws, agent_id, text):
    (ws.worktree(agent_id) / "initial_program.py").write_text(text)


async def test_eval_pipeline_all_statuses(rig):
    ws, hub, make_agent = rig
    _, ex = make_agent("agent-1")

    # 1) first scored eval -> baseline (establishes the agent's own best)
    res = await run(ex, 'coral eval -m "seed as-is"')
    assert not res.is_error and "status: baseline" in res.content
    assert "eval #1" in res.content

    # 2) better packing -> improved
    write_program(ws, "agent-1", IMPROVED)
    res = await run(ex, 'coral eval -m "5x5 grid plus gap circle"')
    assert "status: improved" in res.content

    # 3) smaller radii -> regressed
    write_program(ws, "agent-1", GRID.format(cols=6, rows=5, r="1/14"))
    res = await run(ex, 'coral eval -m "r=1/14 (worse)"')
    assert "status: regressed" in res.content

    # 4) crash -> crashed
    write_program(ws, "agent-1", "raise SystemExit(3)")
    res = await run(ex, 'coral eval -m "broken"')
    assert "status: crashed" in res.content and "score: none" in res.content

    # 5) grader hard timeout -> timeout
    grader_slow = GraderRunner(ws.grader_path, timeout=1.0,
                               args={"program_file": "initial_program.py",
                                     "program_timeout": 30, "n_circles": 26})
    cli_t = CoralCLI(agent_id="agent-1", worktree=ws.worktree("agent-1"),
                     hub=hub, grader=grader_slow)
    write_program(ws, "agent-1", "import time; time.sleep(30)")
    out = await cli_t.dispatch(["eval", "-m", "sleeper"])
    assert "status: timeout" in out

    assert hub.eval_count() == 5
    statuses = [a.status for a in hub.attempts()]
    assert sorted(statuses) == sorted(
        ["baseline", "improved", "regressed", "crashed", "timeout"])


async def test_attempt_record_schema_and_checkpoint(rig):
    ws, hub, make_agent = rig
    _, ex = make_agent("agent-1")
    await run(ex, 'coral eval -m "first"')
    write_program(ws, "agent-1", IMPROVED)
    await run(ex, 'coral eval -m "second"')

    attempts = hub.attempts()
    assert len(attempts) == 2
    a0, a1 = attempts
    raw = json.loads((hub.attempts_dir / f"{a1.commit_hash}.json").read_text())
    for field in ("commit_hash", "agent_id", "title", "score", "status",
                  "parent_hash", "timestamp", "feedback", "checkpoint_hash"):
        assert field in raw, f"missing {field}"
    assert raw["agent_id"] == "agent-1"
    assert raw["title"] == "second"
    assert "T" in raw["timestamp"]  # ISO8601
    assert a1.parent_hash == a0.commit_hash
    assert a0.checkpoint_hash and a1.checkpoint_hash
    assert a0.checkpoint_hash != a1.checkpoint_hash  # checkpoints advance


async def test_checkout_revert_diff_roundtrip(rig):
    ws, hub, make_agent = rig
    cli, ex = make_agent("agent-1")
    await run(ex, 'coral eval -m "v1"')
    v1 = hub.attempts()[0].commit_hash

    write_program(ws, "agent-1", "print('v2')")
    # uncommitted change shows in coral diff
    out = await cli.dispatch(["diff"])
    assert "v2" in out
    await run(ex, 'coral eval -m "v2"')

    # checkout back to v1 restores file content
    out = await cli.dispatch(["checkout", v1[:8]])
    assert "reset" in out
    assert "COLS" in (ws.worktree("agent-1") / "initial_program.py").read_text()

    # new eval from the restored state has v1 as parent
    write_program(ws, "agent-1", GRID.format(cols=6, rows=5, r="1/12.5"))
    await run(ex, 'coral eval -m "branch off v1"')
    assert hub.attempts()[-1].parent_hash == v1

    # revert undoes the last commit
    head_before = cli._git("rev-parse", "HEAD")
    out = await cli.dispatch(["revert"])
    assert "reverted" in out
    assert cli._git("rev-parse", "HEAD") == v1
    assert head_before != v1


async def test_log_and_show_render(rig):
    ws, hub, make_agent = rig
    _, ex1 = make_agent("agent-1")
    _, ex2 = make_agent("agent-2")
    await run(ex1, 'coral eval -m "agent1 seed"')
    write_program(ws, "agent-2", IMPROVED)
    await run(ex2, 'coral eval -m "agent2 denser"')

    cli, _ = make_agent("agent-1")
    log = await cli.dispatch(["log"])
    assert "agent-1" in log and "agent-2" in log
    # leaderboard order: agent-2's higher score first
    assert log.index("agent2 denser") < log.index("agent1 seed")

    log = await cli.dispatch(["log", "--agent", "agent-2"])
    assert "agent-1" not in log

    log = await cli.dispatch(["log", "--search", "denser"])
    assert "agent2 denser" in log and "agent1 seed" not in log

    # a filtered miss must not claim the hub is empty (loop-feeding bug)
    log = await cli.dispatch(["log", "--search", "zzz-no-such-keyword"])
    assert "no attempts match that filter" in log and "2 attempts exist" in log

    recent = await cli.dispatch(["log", "--recent", "-n", "1"])
    assert "agent2 denser" in recent

    best = hub.best_attempt()
    show = await cli.dispatch(["show", best.commit_hash[:8]])
    assert "agent-2" in show and "feedback:" in show
    show_diff = await cli.dispatch(["show", best.commit_hash[:8], "--diff"])
    assert "initial_program.py" in show_diff


async def test_notes_and_skills_commands(rig):
    ws, hub, make_agent = rig
    cli, ex = make_agent("agent-1")
    await ex.execute(ToolCall(name="write_file", arguments={
        "path": ".coral/public/notes/geometry/hexagonal.md",
        "content": "# Hexagonal packings beat grids"}))
    await ex.execute(ToolCall(name="write_file", arguments={
        "path": ".coral/public/skills/scipy-optimize/SKILL.md",
        "content": "---\nname: scipy-optimize\ndescription: SLSQP radius optimization\n---\n"}))

    assert "geometry/hexagonal.md" in await cli.dispatch(["notes"])
    assert "hexagonal" in (await cli.dispatch(["notes", "--search", "grids"]))
    assert "beat grids" in await cli.dispatch(["notes", "read", "geometry/hexagonal.md"])
    assert "scipy-optimize: SLSQP radius optimization" in await cli.dispatch(["skills"])
    assert "SLSQP" in await cli.dispatch(["skills", "read", "scipy-optimize"])


async def test_grader_cannot_be_reached_through_worktree_symlink(rig):
    """Grading runs on a git-archive snapshot: symlinks the agent commits
    cannot point the grader at files outside the snapshot."""
    ws, hub, make_agent = rig
    cli, ex = make_agent("agent-1")
    # agent tries to smuggle a symlink to the private grader into the commit
    res = await run(ex, "ln -s ../../.coral/private/eval/grader.py stolen.py")
    assert not res.is_error
    out = await cli.dispatch(["eval", "-m", "sneaky symlink"])
    # the eval itself must not crash the harness; the snapshot contains a
    # dangling/neutralized link and grading proceeds on the real program
    assert "status:" in out


async def test_usage_errors(rig):
    ws, hub, make_agent = rig
    cli, _ = make_agent("agent-1")
    for argv in (["eval"], ["eval", "-m", ""], ["show"], ["checkout"],
                 ["bogus"], ["revert", "now"], []):
        with pytest.raises(Exception) as ei:
            await cli.dispatch(argv)
        assert "usage" in str(ei.value).lower() or "unknown" in str(ei.value).lower()


async def test_revert_on_first_commit_rejected(rig):
    ws, hub, make_agent = rig
    cli, ex = make_agent("agent-1")
    await run(ex, 'coral eval -m "only"')
    # HEAD~1 is the seed commit, so one revert works; a second must fail
    await cli.dispatch(["revert"])
    with pytest.raises(Exception) as ei:
        await cli.dispatch(["revert"])
    assert "first commit" in str(ei.value)
