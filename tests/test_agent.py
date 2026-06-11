"""M4 gate (model-free): agent loop end-to-end with a scripted engine ---
evals + notes land, nudges fire, forced compaction recovers orientation,
truncation backstop works, trajectory is replayable."""

import json

import pytest

from minicoral.agent import NUDGE, AgentRuntime
from minicoral.config import load_config
from minicoral.coral_cli import CoralCLI
from minicoral.engine import GenResult
from minicoral.grader import GraderRunner
from minicoral.hub import Hub
from minicoral.toolcall import ParseError, ToolCall
from minicoral.tools import ToolExecutor
from minicoral.trajlog import TrajLogger
from minicoral.workspace import build_workspace

IMPROVED = """\
import json
circles = [[(2*i+1)/10, (2*j+1)/10, 0.1] for j in range(5) for i in range(5)]
circles.append([0.2, 0.2, 0.041])
print(json.dumps(circles))
"""


def gen(*calls, text="", errors=()):
    return GenResult(
        text=text,
        tool_calls=[ToolCall(name=n, arguments=a) for n, a in calls],
        finish_reason="tool_calls" if calls else "stop",
        prompt_tokens=100, completion_tokens=20,
        parse_errors=[ParseError(raw="", error=e) for e in errors],
    )


class ScriptedEngine:
    """Plays back a fixed script of GenResults; counts tokens by char/4."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []

    async def generate(self, req):
        self.requests.append(req)
        if not self.script:
            return gen(text="(idle)")
        return self.script.pop(0)

    def count_tokens(self, messages, tools):
        return len(json.dumps(messages)) // 4


@pytest.fixture
def rig(task_yaml, tmp_path):
    cfg = load_config(task_yaml)
    cfg.run.results_dir = str(tmp_path / "results")
    cfg.agents.count = 1
    cfg.grader.args = dict(cfg.grader.args, program_timeout=8)
    ws = build_workspace(cfg, run_ts="m4")
    hub = Hub(ws.public_dir, direction=cfg.grader.direction)
    grader = GraderRunner(ws.grader_path, timeout=cfg.grader.timeout, args=cfg.grader.args)
    cli = CoralCLI(agent_id="agent-1", worktree=ws.worktree("agent-1"), hub=hub, grader=grader)
    executor = ToolExecutor(worktree=ws.worktree("agent-1"), public_dir=ws.public_dir,
                            coral=cli, agent_id="agent-1")
    system_prompt = (ws.worktree("agent-1") / "CORAL.md").read_text()

    def make_runtime(engine, **kw):
        traj = TrajLogger(ws.logs_dir / "agent-1.traj.jsonl", agent_id="agent-1")
        return AgentRuntime(
            "agent-1", engine, executor, hub, traj, system_prompt,
            max_context=10_000_000, compact_at_tokens=9_000_000, **kw,
        ), traj

    return ws, hub, make_runtime


async def test_episode_evals_notes_nudge_trajectory(rig):
    ws, hub, make_runtime = rig
    engine = ScriptedEngine([
        gen(("read_file", {"path": "initial_program.py"})),
        gen(("write_file", {"path": "initial_program.py", "content": IMPROVED})),
        gen(("bash", {"command": 'coral eval -m "5x5 plus gap circle"'})),
        gen(("write_file", {"path": ".coral/public/notes/grids.md",
                            "content": "# 5x5 + gap beats 6x5"})),
        gen(text="thinking out loud"),  # tool-less -> nudge
    ])
    rt, traj = make_runtime(engine, max_turns=6)
    reason = await rt.run()
    assert reason == "max_turns"

    # eval recorded, score improved over nothing -> baseline status, count=1
    attempts = hub.attempts()
    assert len(attempts) == 1 and attempts[0].title == "5x5 plus gap circle"
    assert attempts[0].score == pytest.approx(2.541)
    assert hub.eval_count() == 1
    # note written and visible
    assert (ws.public_dir / "notes" / "grids.md").read_text().startswith("# 5x5")
    # nudge delivered after the tool-less turn
    assert any(m.get("content") == NUDGE for m in rt.messages if m["role"] == "user")

    events = traj.events()
    types = [e["type"] for e in events]
    assert types[0] == "session_start"
    assert types.count("assistant") == 6
    # every tool_call has a matching tool_result
    call_ids = [e["id"] for e in events if e["type"] == "tool_call"]
    result_ids = [e["id"] for e in events if e["type"] == "tool_result"]
    assert call_ids == result_ids and len(call_ids) == 4
    # token counts + gen params present (replayability)
    assert all("prompt_tokens" in e for e in events if e["type"] == "assistant")
    assert "gen_params" in events[0]


async def test_forced_compaction_recovers_orientation(rig):
    ws, hub, make_runtime = rig
    engine = ScriptedEngine([
        gen(("bash", {"command": 'coral eval -m "first eval"'})),
        gen(("bash", {"command": "ls"})),
        gen(("bash", {"command": 'coral eval -m "second eval"'})),
        gen(text="idle"),
    ])
    rt, traj = make_runtime(engine, max_turns=4)
    # tiny high-water: every turn crosses it; reset must wait for an eval boundary
    rt.compact_at_tokens = 10
    rt.max_context = 10_000_000  # keep the truncation backstop out of the way
    await rt.run()

    compactions = [e for e in traj.events() if e["type"] == "compaction"]
    resets = [e for e in compactions if e["strategy"] == "session_reset"]
    assert len(resets) == 2  # once per eval boundary
    assert resets[0]["tokens_before"] > 0 and resets[0]["tokens_after"] > 0

    # after the last reset the session is [system, orientation+eval-result]
    starts = [e for e in traj.events() if e["type"] == "session_start"]
    assert [s["kind"] for s in starts] == ["start", "compaction", "compaction"]
    last = starts[-1]["messages"]
    assert last[0]["role"] == "system"
    user = last[1]["content"]
    assert "Total attempts so far: 2" in user
    assert "coral log" in user  # review-the-leaderboard instruction
    assert "second eval" not in user.split("latest eval result")[0]
    assert "status:" in user  # the eval result rides along
    # turn counter survives the reset
    assert rt.turn == 4


async def test_no_compaction_without_eval_boundary(rig):
    ws, hub, make_runtime = rig
    engine = ScriptedEngine([gen(("bash", {"command": "ls"})) for _ in range(3)])
    rt, traj = make_runtime(engine, max_turns=3)
    rt.compact_at_tokens = 10
    await rt.run()
    assert not [e for e in traj.events()
                if e["type"] == "compaction" and e["strategy"] == "session_reset"]


async def test_truncation_backstop(rig):
    ws, hub, make_runtime = rig
    big = "x" * 4000
    engine = ScriptedEngine([gen(("bash", {"command": f"echo {big}"})) for _ in range(4)])
    rt, traj = make_runtime(engine, max_turns=4)
    rt.compact_at_tokens = 2000
    rt.max_context = 4000
    rt.max_new_tokens = 100
    await rt.run()

    truncs = [e for e in traj.events() if e["type"] == "compaction"
              and e["strategy"] == "truncate"]
    assert truncs and truncs[0]["dropped_messages"] > 0
    assert rt.messages[0]["role"] == "system"  # system prompt always survives
    assert rt.messages[1].get("role") != "tool"  # no orphaned tool results
    # the backstop's job: keep room for generation under max_context
    assert rt._count_tokens() <= rt.max_context - rt.max_new_tokens


async def test_parse_error_fed_back(rig):
    ws, hub, make_runtime = rig
    engine = ScriptedEngine([gen(errors=("invalid JSON in <tool_call>",))])
    rt, traj = make_runtime(engine, max_turns=1)
    await rt.run()
    feedback = [m for m in rt.messages if m["role"] == "user"
                and "could not be executed" in m.get("content", "")]
    assert feedback and "invalid JSON" in feedback[0]["content"]
    assert any(e["type"] == "error" for e in traj.events())


async def test_heartbeat_prompts_ride_eval_results_into_trajectory(rig):
    """M5 integration: reflect (every eval) is appended to the eval tool result
    and therefore lands in the trajectory the model actually saw."""
    from minicoral.config import DEFAULT_HEARTBEATS, HeartbeatAction
    from minicoral.heartbeat import HeartbeatMonitor

    ws, hub, make_runtime = rig
    engine = ScriptedEngine([
        gen(("bash", {"command": 'coral eval -m "first"'})),
        gen(("bash", {"command": 'coral eval -m "second"'})),
    ])
    rt, traj = make_runtime(engine, max_turns=2)
    rt.executor.coral.heartbeat = HeartbeatMonitor(
        [HeartbeatAction(**a) for a in DEFAULT_HEARTBEATS],
        heartbeat_dir=ws.public_dir / "heartbeat",
    )
    await rt.run()

    results = [e for e in traj.events() if e["type"] == "tool_result"]
    hb = [e for e in results if "--- HEARTBEAT ---" in e["content"]]
    assert len(hb) == 2  # reflect fires on every eval
    assert "Pause and reflect" in hb[0]["content"]
    # observability mirror updated through the real eval path
    assert (ws.public_dir / "heartbeat" / "agent-1.json").exists()


async def test_capture_states_follows_transport(rig):
    ws, hub, make_runtime = rig

    class WantsCapture:
        def wants_capture(self):
            return True

    engine = ScriptedEngine([gen(text="hi")])
    rt, _ = make_runtime(engine, max_turns=1)
    rt.transport = WantsCapture()
    await rt.run()
    assert engine.requests[0].capture_states is True

    engine2 = ScriptedEngine([gen(text="hi")])
    rt2, _ = make_runtime(engine2, max_turns=1)
    await rt2.run()
    assert engine2.requests[0].capture_states is False
