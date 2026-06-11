"""M6 gate (model-free): multi-agent orchestration --- interleaved attempts,
global consolidate routing, dead-agent restart with orientation, clean stops."""

import json
import re

import pytest

import minicoral.orchestrator as orch_mod
from minicoral.config import load_config
from minicoral.engine import GenResult
from minicoral.orchestrator import Orchestrator
from minicoral.toolcall import ToolCall


def gen(*calls, text=""):
    return GenResult(
        text=text,
        tool_calls=[ToolCall(name=n, arguments=a) for n, a in calls],
        finish_reason="tool_calls" if calls else "stop",
        prompt_tokens=50, completion_tokens=10,
    )


def eval_call(msg):
    return gen(("bash", {"command": f'coral eval -m "{msg}"'}))


class RouterEngine:
    """Routes scripted GenResults per agent (identified from the system prompt)."""

    def __init__(self, scripts: dict[str, list], raise_once_for: set[str] = ()):
        self.scripts = {k: list(v) for k, v in scripts.items()}
        self.raise_once_for = set(raise_once_for)
        self.requests = []

    def _agent_of(self, req) -> str:
        m = re.search(r"You are (agent-\d+)\.", req.messages[0]["content"])
        return m.group(1)

    async def generate(self, req):
        agent = self._agent_of(req)
        self.requests.append(agent)
        if agent in self.raise_once_for:
            self.raise_once_for.discard(agent)
            raise RuntimeError("engine exploded")
        script = self.scripts.get(agent, [])
        return script.pop(0) if script else gen(text="(idle)")

    def count_tokens(self, messages, tools):
        return len(json.dumps(messages)) // 4


@pytest.fixture(autouse=True)
def fast_timing(monkeypatch):
    monkeypatch.setattr(orch_mod, "STAGGER_SECONDS", 0.01)
    monkeypatch.setattr(orch_mod, "RESTART_BACKOFF_SECONDS", 0.02)


def make_cfg(task_yaml, tmp_path, **run_kw):
    cfg = load_config(task_yaml)
    cfg.run.results_dir = str(tmp_path / "results")
    cfg.grader.args = dict(cfg.grader.args, program_timeout=8)
    for k, v in run_kw.items():
        setattr(cfg.run, k, v)
    return cfg


async def test_two_agents_interleave_and_stop_cleanly(task_yaml, tmp_path):
    cfg = make_cfg(task_yaml, tmp_path, wall_clock_hours=0.0005)  # 1.8s budget
    cfg.agents.count = 2
    cfg.agents.max_turns = 3
    engine = RouterEngine({
        "agent-1": [eval_call("a1 first"), gen(text="done")],
        "agent-2": [eval_call("a2 first"), gen(text="done")],
    })
    orch = Orchestrator(cfg, engine=engine, run_ts="t1")
    reason = await orch.run()

    attempts = orch.hub.attempts()
    assert {a.agent_id for a in attempts} == {"agent-1", "agent-2"}
    assert orch.hub.eval_count() == 2
    assert "wall clock" in reason

    run_events = orch.run_log.events()
    types = [e["type"] for e in run_events]
    assert types[0] == "run_start" and types[-1] == "run_stop"
    assert types.count("agent_start") == 2
    assert run_events[-1]["reason"] == reason
    # per-agent eval events landed in the right trajectory
    a1_evals = [e for e in orch.traj["agent-1"].events() if e["type"] == "eval"]
    assert len(a1_evals) == 1 and a1_evals[0]["title"] == "a1 first"


async def test_consolidate_fires_exactly_once_at_global_10(task_yaml, tmp_path):
    cfg = make_cfg(task_yaml, tmp_path, wall_clock_hours=0.003)
    cfg.agents.count = 2
    cfg.agents.max_turns = 12
    # all 10 evals score the same: #1 sets the best, 2-10 go stale; the run
    # stops itself right after global eval #10 (no wall-clock waiting)
    cfg.run.max_stale_evals = 9
    engine = RouterEngine({
        "agent-1": [eval_call(f"a1 #{i}") for i in range(3)],
        "agent-2": [eval_call(f"a2 #{i}") for i in range(7)],
    })
    orch = Orchestrator(cfg, engine=engine, run_ts="t2")
    await orch.run()

    assert orch.hub.eval_count() == 10
    fires = []
    for agent_id in ("agent-1", "agent-2"):
        fires += [e for e in orch.traj[agent_id].events()
                  if e["type"] == "heartbeat" and e["action"] == "consolidate"]
    assert len(fires) == 1  # exactly one agent crossed global eval #10
    g = json.loads((orch.ws.public_dir / "heartbeat" / "global.json").read_text())
    assert g["fired"]["consolidate"] == 1 and g["eval_count"] == 10


async def test_crashed_agent_restarts_with_orientation(task_yaml, tmp_path):
    cfg = make_cfg(task_yaml, tmp_path, wall_clock_hours=0.0008)
    cfg.agents.count = 2
    cfg.agents.max_turns = 4
    engine = RouterEngine(
        {"agent-1": [eval_call("a1 work")], "agent-2": []},
        raise_once_for={"agent-2"},
    )
    orch = Orchestrator(cfg, engine=engine, run_ts="t3")
    await orch.run()

    a2 = orch.traj["agent-2"].events()
    assert any(e["type"] == "error" and "engine exploded" in e["error"] for e in a2)
    assert any(e["type"] == "agent_restart" for e in a2)
    assert orch.state.restarts.get("agent-2", 0) >= 1
    # the restarted session opens with the 5-point orientation block
    starts = [e for e in a2 if e["type"] == "session_start"]
    restarted = starts[1]["messages"][1]["content"]
    assert "Total attempts so far:" in restarted
    assert "coral log" in restarted


async def test_max_turns_exhaustion_triggers_restart(task_yaml, tmp_path):
    cfg = make_cfg(task_yaml, tmp_path, wall_clock_hours=0.0005)
    cfg.agents.count = 1
    cfg.agents.max_turns = 2
    engine = RouterEngine({"agent-1": []})  # idles every turn
    orch = Orchestrator(cfg, engine=engine, run_ts="t4")
    await orch.run()

    stops = [e for e in orch.run_log.events() if e["type"] == "agent_stop"]
    assert any(e["reason"] == "max_turns" for e in stops)
    assert orch.state.restarts.get("agent-1", 0) >= 1


async def test_global_stale_stop(task_yaml, tmp_path):
    cfg = make_cfg(task_yaml, tmp_path, wall_clock_hours=0.01, max_stale_evals=3)
    cfg.agents.count = 1
    cfg.agents.max_turns = 10
    # 5 evals of identical score: #1 sets the global best, 2-4 go stale
    engine = RouterEngine({"agent-1": [eval_call(f"same #{i}") for i in range(5)]})
    orch = Orchestrator(cfg, engine=engine, run_ts="t5")
    reason = await orch.run()

    assert "no global improvement" in reason
    assert orch.state.stale_evals == 3
    assert orch.hub.eval_count() == 4  # stopped before exhausting the script
