"""M0 gate: config loading/overrides + prompt rendering."""

import yaml

from minicoral import prompts
from minicoral.config import load_config


def test_load_task_yaml(task_yaml):
    cfg = load_config(task_yaml)
    assert "Circle Packing" in cfg.task.name
    assert cfg.grader.direction == "maximize"
    assert cfg.grader.timeout == 300
    assert cfg.agents.count == 4
    assert [h.name for h in cfg.agents.heartbeat] == ["reflect", "consolidate", "pivot"]
    assert cfg.agents.heartbeat[1].scope == "global"
    assert cfg.agents.heartbeat[2].trigger == "plateau"
    assert cfg.engine.backend == "hf"
    assert cfg.engine.compact_at_tokens == 24576
    assert cfg.task.seed_dir.is_dir()


def test_override_deep_merge(task_yaml, tmp_path):
    ov = tmp_path / "ov.yaml"
    ov.write_text(yaml.safe_dump({
        "engine": {"backend": "api", "temperature": 0.2},
        "agents": {"count": 2},
        "run": {"wall_clock_hours": 0.5},
    }))
    cfg = load_config(task_yaml, ov)
    assert cfg.engine.backend == "api"
    assert cfg.engine.temperature == 0.2
    assert cfg.engine.max_context == 32768  # untouched by override
    assert cfg.agents.count == 2
    assert cfg.run.wall_clock_hours == 0.5


def test_unknown_key_rejected(task_yaml, tmp_path):
    ov = tmp_path / "ov.yaml"
    ov.write_text(yaml.safe_dump({"engine": {"bogus_knob": 1}}))
    try:
        load_config(task_yaml, ov)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "bogus_knob" in str(e)


def test_resolved_dump_roundtrip(task_yaml, tmp_path):
    cfg = load_config(task_yaml)
    out = tmp_path / "config.resolved.yaml"
    cfg.dump_resolved(out)
    data = yaml.safe_load(out.read_text())
    assert data["engine"]["max_context"] == 32768
    assert data["agents"]["heartbeat"][0]["name"] == "reflect"


def test_coral_md_renders_all_placeholders():
    text = prompts.render_coral_md(
        multi_agent=True,
        task_name="T", task_description="D", score_direction="higher is better",
        shared_dir="/shared/.coral/public", agent_id="agent-1",
    )
    assert "{" not in text.replace("{0,1}", "")  # no unfilled placeholders
    assert "You are agent-1." in text
    assert "one of several agents" in text
    assert "## Runtime Tools" in text
    single = prompts.render_coral_md(
        multi_agent=False,
        task_name="T", task_description="D", score_direction="higher is better",
        shared_dir="/s", agent_id="agent-1",
    )
    assert "never stop until you reach / beat the best score" in single
    assert "colleagues" not in single
    assert "from previous runs" in single


def test_heartbeat_prompts_render():
    for name in ("reflect", "consolidate", "pivot"):
        text = prompts.render_heartbeat(name, shared_dir="/s", agent_id="agent-2")
        assert "{shared_dir}" not in text and "{agent_id}" not in text
    assert "coral log --agent agent-2" in prompts.render_heartbeat(
        "pivot", shared_dir="/s", agent_id="agent-2")


def test_restart_orientation_renders():
    text = prompts.render_restart_orientation(
        attempt_count=12, own_attempt_count=3, best_score=2.31, own_best_score=None,
        score_direction="higher is better", shared_dir="/s", agent_id="agent-1",
    )
    assert "12" in text and "2.31" in text and "none yet" in text
    assert "coral log" in text
