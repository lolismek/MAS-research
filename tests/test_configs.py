"""Wrap-up gate: the shipped override configs parse and resolve sensibly."""

from pathlib import Path

from minicoral.config import load_config

CONFIGS = Path(__file__).resolve().parent.parent / "configs"


def test_dev_mps(task_yaml):
    cfg = load_config(task_yaml, CONFIGS / "dev-mps.yaml")
    assert cfg.engine.backend == "hf" and cfg.engine.device == "mps"
    assert cfg.engine.dtype == "float16"
    assert cfg.agents.count == 2 and cfg.agents.model == "Qwen/Qwen3-4B"
    assert cfg.run.wall_clock_hours == 0.5


def test_gpu_a100(task_yaml):
    cfg = load_config(task_yaml, CONFIGS / "gpu-a100.yaml")
    assert cfg.engine.device == "cuda" and cfg.engine.dtype == "bfloat16"
    assert cfg.agents.count == 4 and cfg.agents.model == "Qwen/Qwen3-8B"
    assert cfg.engine.max_context == 32768
    assert cfg.run.wall_clock_hours == 3.0


def test_api_gpt54mini(task_yaml):
    cfg = load_config(task_yaml, CONFIGS / "api-gpt54mini.yaml")
    assert cfg.engine.backend == "api"
    assert cfg.engine.base_url == "https://api.perplexity.ai"
    assert cfg.engine.api_key_env == "PERPLEXITY_API_KEY"
    assert cfg.agents.count == 1 and cfg.agents.model == "gpt-5.4-mini"
    # heartbeats and grader stay paper-default under all overrides
    assert [h.name for h in cfg.agents.heartbeat] == ["reflect", "consolidate", "pivot"]
    assert cfg.grader.timeout == 300
