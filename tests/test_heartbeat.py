"""M5 gate: heartbeat trigger math --- intervals (local+global), plateau with
cooldown (no refire at 6-9 stale, refire at 10), reset on improvement,
prompts in eval output / trajectory."""

import json

from minicoral.config import DEFAULT_HEARTBEATS, HeartbeatAction
from minicoral.heartbeat import HeartbeatMonitor
from minicoral.hub import Attempt


def attempt(status, agent_id="agent-1"):
    return Attempt(
        commit_hash="c" * 40, agent_id=agent_id, title="t", score=1.0,
        status=status, parent_hash=None, timestamp="2026-06-11T00:00:00+00:00",
        feedback="f",
    )


def default_monitor(**kw):
    return HeartbeatMonitor([HeartbeatAction(**a) for a in DEFAULT_HEARTBEATS], **kw)


def test_reflect_fires_every_eval():
    m = HeartbeatMonitor([HeartbeatAction("reflect", 1, "interval", "local")])
    for g in range(1, 4):
        prompts = m.on_eval("agent-1", attempt("improved"), g)
        assert len(prompts) == 1 and "reflect" in prompts[0].lower()


def test_interval_local_counts_per_agent():
    m = HeartbeatMonitor([HeartbeatAction("reflect", 2, "interval", "local")])
    assert m.on_eval("agent-1", attempt("improved"), 1) == []
    assert m.on_eval("agent-2", attempt("improved", "agent-2"), 2) == []  # a2 local=1
    assert len(m.on_eval("agent-1", attempt("improved"), 3)) == 1  # a1 local=2
    assert len(m.on_eval("agent-2", attempt("improved", "agent-2"), 4)) == 1


def test_consolidate_global_lands_on_crossing_agent():
    m = HeartbeatMonitor([HeartbeatAction("consolidate", 10, "interval", "global")])
    # agents alternate; eval #10 happens to be agent-2's
    for g in range(1, 10):
        agent = f"agent-{1 + (g - 1) % 2}"
        assert m.on_eval(agent, attempt("improved", agent), g) == []
    prompts = m.on_eval("agent-2", attempt("improved", "agent-2"), 10)
    assert len(prompts) == 1 and "synthesize the shared knowledge base" in prompts[0]


def test_pivot_cooldown_no_refire_until_10():
    m = HeartbeatMonitor([HeartbeatAction("pivot", 5, "plateau", "local")])
    fires = []
    for i in range(1, 13):  # 12 consecutive non-improving evals
        prompts = m.on_eval("agent-1", attempt("regressed"), i)
        if prompts:
            fires.append(i)
    # fire at stale=5; cooldown holds through 6-9; refire at 10; not yet at 12
    assert fires == [5, 10]


def test_pivot_resets_on_improvement():
    m = HeartbeatMonitor([HeartbeatAction("pivot", 5, "plateau", "local")])
    for i in range(1, 6):
        m.on_eval("agent-1", attempt("regressed"), i)
    assert m._state("agent-1").stale == 5
    m.on_eval("agent-1", attempt("improved"), 6)
    assert m._state("agent-1").stale == 0
    # plateau must build up 5 fresh stale evals again
    fires = []
    for i in range(7, 12):
        if m.on_eval("agent-1", attempt("baseline"), i):
            fires.append(i)
    assert fires == [11]


def test_crashed_and_timeout_count_as_stale():
    m = HeartbeatMonitor([HeartbeatAction("pivot", 5, "plateau", "local")])
    statuses = ["baseline", "crashed", "timeout", "regressed", "crashed"]
    fired = []
    for i, s in enumerate(statuses, 1):
        if m.on_eval("agent-1", attempt(s), i):
            fired.append(i)
    assert fired == [5]


def test_default_stack_at_eval_10_stale_5():
    m = default_monitor()
    # 4 non-improving evals, then the 5th is also global eval #10
    for g in range(6, 10):
        m.on_eval("agent-1", attempt("regressed"), g)
    prompts = m.on_eval("agent-1", attempt("regressed"), 10)
    # reflect (every eval) + consolidate (global 10) + pivot (stale 5)
    assert len(prompts) == 3


def test_prompts_render_substitutions():
    m = HeartbeatMonitor([HeartbeatAction("pivot", 1, "plateau", "local")],
                         shared_dir="SHARED")
    [p] = m.on_eval("agent-7", attempt("regressed", "agent-7"), 1)
    assert "coral log --agent agent-7" in p and "SHARED/notes" not in p
    assert "{shared_dir}" not in p and "{agent_id}" not in p


def test_custom_prompt_action():
    m = HeartbeatMonitor([HeartbeatAction("focus", 1, "interval", "local",
                                          prompt="Stay focused, {agent_id}.")])
    [p] = m.on_eval("agent-1", attempt("improved"), 1)
    assert p == "Stay focused, agent-1."


def test_state_mirrored_to_files(tmp_path):
    m = default_monitor(heartbeat_dir=tmp_path)
    m.on_eval("agent-1", attempt("regressed"), 1)
    m.on_eval("agent-1", attempt("regressed"), 2)
    state = json.loads((tmp_path / "agent-1.json").read_text())
    assert state["local_count"] == 2 and state["stale"] == 2
    assert state["fired"]["reflect"] == 2
    g = json.loads((tmp_path / "global.json").read_text())
    assert g["eval_count"] == 2
    assert [a["name"] for a in g["actions"]] == ["reflect", "consolidate", "pivot"]


def test_on_fire_callback():
    seen = []
    m = HeartbeatMonitor([HeartbeatAction("reflect", 1, "interval", "local")],
                         on_fire=lambda aid, name, prompt: seen.append((aid, name)))
    m.on_eval("agent-1", attempt("improved"), 1)
    assert seen == [("agent-1", "reflect")]


def test_describe_renders_table():
    text = default_monitor().describe()
    assert "reflect" in text and "consolidate" in text and "pivot" in text
    assert "plateau" in text and "global" in text
