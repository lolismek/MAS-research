"""Orchestrator: build the run, drive N agent tasks, terminate, restart.

Lifecycle (paper C.6): build workspace -> seed heartbeat config -> per agent:
worktree+symlinks+CORAL.md (workspace.py), CLI/executor/runtime -> N asyncio
tasks with staggered start -> monitoring via callbacks.

Termination: wall-clock budget, global no-improvement stop (max_stale_evals
consecutive evals without a new global best), per-session max_turns ->
dead-agent restart with the C.6 orientation prompt (also on crash).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from .agent import AgentRuntime
from .config import Config
from .coral_cli import CoralCLI
from .engine import Engine, build_engine
from .grader import GraderRunner
from .heartbeat import HeartbeatMonitor
from .hub import Attempt, Hub
from .tools import ToolExecutor
from .trajlog import TrajLogger
from .transport import build_transport
from .workspace import Workspace, build_workspace

STAGGER_SECONDS = 2.0
RESTART_BACKOFF_SECONDS = 5.0


@dataclass
class RunState:
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    stop_reason: str | None = None
    global_best: float | None = None
    stale_evals: int = 0
    restarts: dict[str, int] = field(default_factory=dict)

    def request_stop(self, reason: str) -> None:
        if not self.stop_event.is_set():
            self.stop_reason = reason
            self.stop_event.set()


class Orchestrator:
    def __init__(self, cfg: Config, *, engine: Engine | None = None,
                 run_ts: str | None = None):
        self.cfg = cfg
        self.ws: Workspace = build_workspace(cfg, run_ts=run_ts)
        self.hub = Hub(self.ws.public_dir, direction=cfg.grader.direction)
        self.engine = engine or build_engine(cfg.engine, cfg.agents.model)
        self.grader = GraderRunner(self.ws.grader_path, timeout=cfg.grader.timeout,
                                   args=cfg.grader.args)
        self.transport = build_transport(cfg.transport.kind, self.ws.sidecars_dir)
        self.state = RunState()
        self.run_log = TrajLogger(self.ws.run_dir / "run.events.jsonl")
        self.traj: dict[str, TrajLogger] = {
            agent_id: TrajLogger(self.ws.logs_dir / f"{agent_id}.traj.jsonl",
                                 agent_id=agent_id)
            for agent_id in self.ws.agent_ids()
        }
        self.heartbeat = HeartbeatMonitor(
            cfg.agents.heartbeat,
            shared_dir=Workspace.AGENT_SHARED_DIR,
            heartbeat_dir=self.ws.public_dir / "heartbeat",
            on_fire=self._on_heartbeat_fire,
        )

    # -- callbacks -------------------------------------------------------------

    def _on_heartbeat_fire(self, agent_id: str, action: str, prompt: str) -> None:
        self.traj[agent_id].log("heartbeat", action=action, prompt=prompt)

    def _on_eval(self, attempt: Attempt) -> None:
        self.traj[attempt.agent_id].log(
            "eval", commit_hash=attempt.commit_hash, score=attempt.score,
            status=attempt.status, title=attempt.title,
        )
        better = attempt.score is not None and (
            self.state.global_best is None
            or (attempt.score > self.state.global_best
                if self.cfg.grader.direction == "maximize"
                else attempt.score < self.state.global_best)
        )
        if better:
            self.state.global_best = attempt.score
            self.state.stale_evals = 0
        else:
            self.state.stale_evals += 1
            if self.state.stale_evals >= self.cfg.run.max_stale_evals:
                self.state.request_stop(
                    f"no global improvement in {self.state.stale_evals} evals"
                )

    # -- agent wiring ------------------------------------------------------------

    def _make_runtime(self, agent_id: str, restart: bool) -> AgentRuntime:
        worktree = self.ws.worktree(agent_id)
        cli = CoralCLI(
            agent_id=agent_id, worktree=worktree, hub=self.hub,
            grader=self.grader, heartbeat=self.heartbeat, on_eval=self._on_eval,
        )
        executor = ToolExecutor(
            worktree=worktree, public_dir=self.ws.public_dir,
            coral=cli, transport=self.transport, agent_id=agent_id,
            tool_output_max_chars=self.cfg.engine.tool_output_max_chars,
        )
        e = self.cfg.engine
        return AgentRuntime(
            agent_id, self.engine, executor, self.hub, self.traj[agent_id],
            system_prompt=(worktree / "CORAL.md").read_text(),
            max_turns=self.cfg.agents.max_turns,
            max_context=e.max_context,
            compact_at_tokens=e.compact_at_tokens,
            max_new_tokens=e.max_new_tokens,
            temperature=e.temperature,
            thinking=e.thinking,
            seed=self.cfg.run.seed,
            score_direction_text=self.cfg.grader.score_direction_text,
            shared_dir=Workspace.AGENT_SHARED_DIR,
            restart_orientation=restart,
            transport=self.transport,
        )

    async def _agent_task(self, agent_id: str, stagger: float) -> None:
        await asyncio.sleep(stagger)
        restart = False
        while not self.state.stop_event.is_set():
            self.run_log.log(
                "agent_restart" if restart else "agent_start",
                agent_id=agent_id, restarts=self.state.restarts.get(agent_id, 0),
            )
            if restart:
                self.traj[agent_id].log(
                    "agent_restart", restarts=self.state.restarts.get(agent_id, 0))
            try:
                runtime = self._make_runtime(agent_id, restart)
                reason = await runtime.run(self.state.stop_event)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.traj[agent_id].log("error", error=f"agent died: {e!r}")
                reason = f"crashed: {e!r}"
            self.run_log.log("agent_stop", agent_id=agent_id, reason=reason)
            if reason == "stopped" or self.state.stop_event.is_set():
                return
            # max_turns exhaustion or crash -> dead-agent restart (C.6)
            self.state.restarts[agent_id] = self.state.restarts.get(agent_id, 0) + 1
            restart = True
            await asyncio.sleep(RESTART_BACKOFF_SECONDS)

    # -- run --------------------------------------------------------------------

    async def run(self) -> str:
        cfg = self.cfg
        self.run_log.log(
            "run_start", run_dir=str(self.ws.run_dir), agents=self.ws.agent_ids(),
            backend=cfg.engine.backend, model=cfg.agents.model,
            wall_clock_hours=cfg.run.wall_clock_hours,
        )
        tasks = [
            asyncio.create_task(self._agent_task(agent_id, i * STAGGER_SECONDS),
                                name=agent_id)
            for i, agent_id in enumerate(self.ws.agent_ids())
        ]

        budget = cfg.run.wall_clock_hours * 3600
        try:
            await asyncio.wait_for(
                asyncio.shield(asyncio.gather(*tasks, return_exceptions=True)),
                timeout=budget,
            )
            if self.state.stop_reason is None:
                self.state.request_stop("all agents finished")
        except asyncio.TimeoutError:
            self.state.request_stop(f"wall clock budget ({cfg.run.wall_clock_hours}h)")
            # graceful: agents notice stop_event after their current turn
            await asyncio.gather(*tasks, return_exceptions=True)

        reason = self.state.stop_reason or "done"
        self.run_log.log(
            "run_stop", reason=reason,
            eval_count=self.hub.eval_count(),
            global_best=self.state.global_best,
        )
        return reason


async def run_orchestrator(cfg: Config) -> int:
    orch = Orchestrator(cfg)
    reason = await orch.run()
    best = orch.hub.best_attempt()
    print(f"run finished: {reason}")
    print(f"run dir: {orch.ws.run_dir}")
    print(f"evals: {orch.hub.eval_count()}")
    if best is not None:
        print(f"best: {best.score:.6g} by {best.agent_id} ({best.commit_hash[:8]})")
    return 0
