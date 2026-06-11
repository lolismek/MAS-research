"""YAML task config -> dataclasses (paper Appendix D.1 schema, mini-CORAL subset).

Sections: task, grader, agents, engine, run, transport, sharing. An optional
override YAML (-o) is deep-merged on top of the task file. Paths in `task`
(seed dir, grader private files) are resolved relative to the task.yaml
location.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TaskConfig:
    name: str
    description: str
    files: list[str] = field(default_factory=list)
    tips: str = ""
    seed: str = "seed"  # dir of initial files, relative to task.yaml
    task_dir: Path = Path(".")  # resolved location of task.yaml

    @property
    def seed_dir(self) -> Path:
        return (self.task_dir / self.seed).resolve()


@dataclass
class GraderConfig:
    timeout: float = 300.0
    direction: str = "maximize"  # or "minimize"
    args: dict[str, Any] = field(default_factory=dict)
    private: list[str] = field(default_factory=lambda: ["eval/"])

    def __post_init__(self):
        if self.direction not in ("maximize", "minimize"):
            raise ValueError(f"grader.direction must be maximize|minimize, got {self.direction!r}")

    @property
    def score_direction_text(self) -> str:
        return "higher is better" if self.direction == "maximize" else "lower is better"


@dataclass
class HeartbeatAction:
    name: str
    every: int
    trigger: str  # "interval" | "plateau"
    scope: str  # "local" | "global"
    prompt: str | None = None  # None -> built-in paper prompt by name

    def __post_init__(self):
        if self.trigger not in ("interval", "plateau"):
            raise ValueError(f"heartbeat trigger must be interval|plateau, got {self.trigger!r}")
        if self.scope not in ("local", "global"):
            raise ValueError(f"heartbeat scope must be local|global, got {self.scope!r}")


# Paper Table 7 defaults.
DEFAULT_HEARTBEATS = [
    {"name": "reflect", "every": 1, "trigger": "interval", "scope": "local"},
    {"name": "consolidate", "every": 10, "trigger": "interval", "scope": "global"},
    {"name": "pivot", "every": 5, "trigger": "plateau", "scope": "local"},
]


@dataclass
class AgentsConfig:
    count: int = 4
    model: str = "Qwen/Qwen3-8B"
    max_turns: int = 200
    heartbeat: list[HeartbeatAction] = field(default_factory=list)


@dataclass
class EngineConfig:
    backend: str = "hf"  # "hf" | "api"
    device: str = "auto"
    dtype: str = "bfloat16"
    max_context: int = 32768
    compact_at_tokens: int = 24576
    max_new_tokens: int = 2048
    temperature: float = 0.7
    thinking: bool = False
    tool_output_max_chars: int = 2000
    base_url: str | None = None  # api backend; falls back to OPENAI_BASE_URL/.env
    api_key_env: str = "OPENAI_API_KEY"

    def __post_init__(self):
        if self.backend not in ("hf", "api"):
            raise ValueError(f"engine.backend must be hf|api, got {self.backend!r}")


@dataclass
class RunConfig:
    wall_clock_hours: float = 3.0
    max_stale_evals: int = 40  # global no-improvement stop
    results_dir: str = "results"
    seed: int | None = None


@dataclass
class TransportConfig:
    kind: str = "text_only"


@dataclass
class SharingConfig:
    attempts: bool = True
    notes: bool = True
    skills: bool = True


@dataclass
class Config:
    task: TaskConfig
    grader: GraderConfig
    agents: AgentsConfig
    engine: EngineConfig
    run: RunConfig
    transport: TransportConfig
    sharing: SharingConfig

    def to_dict(self) -> dict:
        d = asdict(self)
        d["task"]["task_dir"] = str(self.task.task_dir)
        return d

    def dump_resolved(self, path: Path) -> None:
        path.write_text(yaml.safe_dump(self.to_dict(), sort_keys=False))


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _only_known(section: str, raw: dict, cls) -> dict:
    known = set(cls.__dataclass_fields__)
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"unknown keys in {section}: {sorted(unknown)}")
    return raw


def load_config(task_yaml: Path, override_yaml: Path | None = None) -> Config:
    task_yaml = Path(task_yaml).resolve()
    raw = yaml.safe_load(task_yaml.read_text()) or {}
    if override_yaml is not None:
        override = yaml.safe_load(Path(override_yaml).read_text()) or {}
        raw = _deep_merge(raw, override)

    task_raw = dict(raw.get("task") or {})
    task_raw.pop("task_dir", None)
    task = TaskConfig(task_dir=task_yaml.parent, **_only_known("task", task_raw, TaskConfig))

    grader = GraderConfig(**_only_known("grader", dict(raw.get("grader") or {}), GraderConfig))

    agents_raw = dict(raw.get("agents") or {})
    hb_raw = agents_raw.pop("heartbeat", None)
    if hb_raw is None:
        hb_raw = DEFAULT_HEARTBEATS
    heartbeat = [HeartbeatAction(**dict(h)) for h in hb_raw]
    agents = AgentsConfig(heartbeat=heartbeat, **_only_known("agents", agents_raw, AgentsConfig))

    engine = EngineConfig(**_only_known("engine", dict(raw.get("engine") or {}), EngineConfig))
    run = RunConfig(**_only_known("run", dict(raw.get("run") or {}), RunConfig))
    transport = TransportConfig(**_only_known("transport", dict(raw.get("transport") or {}), TransportConfig))
    sharing = SharingConfig(**_only_known("sharing", dict(raw.get("sharing") or {}), SharingConfig))

    return Config(
        task=task, grader=grader, agents=agents, engine=engine,
        run=run, transport=transport, sharing=sharing,
    )
