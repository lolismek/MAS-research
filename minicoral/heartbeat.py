"""HeartbeatMonitor: paper Table 7 trigger state machine.

- interval triggers fire when count % every == 0, on the local (per-agent) or
  global eval counter depending on scope.
- plateau triggers fire when consecutive non-improving evals >= every, with a
  cooldown that prevents re-firing until another `every` evals of continued
  stalling (fire at 5, then 10, 15, ... until an improvement resets).

Delivery is adapted from the paper's SIGINT+resume: CoralCLI appends the
rendered prompts to the eval result (eval-boundary delivery, equivalent
semantics --- context injected without discarding the session).

Driven by on_eval(agent_id, attempt, global_count) -> list of rendered
prompts. Pure state machine; per-agent state is mirrored to
.coral/public/heartbeat/*.json for observability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import HeartbeatAction
from .hub import Attempt
from .prompts import HEARTBEAT_PROMPTS


@dataclass
class _AgentState:
    local_count: int = 0
    stale: int = 0  # consecutive evals without improvement
    last_pivot_stale: dict[str, int] = field(default_factory=dict)  # action -> stale at last fire
    fired: dict[str, int] = field(default_factory=dict)  # action -> total fires


class HeartbeatMonitor:
    def __init__(
        self,
        actions: list[HeartbeatAction],
        shared_dir: str = ".coral/public",
        heartbeat_dir: Path | None = None,  # .coral/public/heartbeat mirror
        on_fire: Callable[[str, str, str], None] | None = None,
    ):
        self.actions = actions
        self.shared_dir = shared_dir
        self.heartbeat_dir = heartbeat_dir
        self.on_fire = on_fire
        self._agents: dict[str, _AgentState] = {}
        self._global_fired: dict[str, int] = {}

    def _state(self, agent_id: str) -> _AgentState:
        return self._agents.setdefault(agent_id, _AgentState())

    def _render(self, action: HeartbeatAction, agent_id: str) -> str:
        template = action.prompt or HEARTBEAT_PROMPTS[action.name]
        return template.format(shared_dir=self.shared_dir, agent_id=agent_id)

    def on_eval(self, agent_id: str, attempt: Attempt, global_count: int) -> list[str]:
        st = self._state(agent_id)
        st.local_count += 1
        if attempt.status == "improved":
            st.stale = 0
            st.last_pivot_stale.clear()
        else:
            st.stale += 1

        prompts: list[str] = []
        for action in self.actions:
            if self._triggered(action, st, global_count):
                st.fired[action.name] = st.fired.get(action.name, 0) + 1
                if action.scope == "global":
                    self._global_fired[action.name] = (
                        self._global_fired.get(action.name, 0) + 1
                    )
                prompt = self._render(action, agent_id)
                prompts.append(prompt)
                if self.on_fire is not None:
                    self.on_fire(agent_id, action.name, prompt)

        self._mirror(agent_id, global_count)
        return prompts

    def _triggered(self, action: HeartbeatAction, st: _AgentState, global_count: int) -> bool:
        if action.trigger == "interval":
            count = global_count if action.scope == "global" else st.local_count
            return count > 0 and count % action.every == 0
        # plateau with cooldown
        if st.stale < action.every:
            return False
        last = st.last_pivot_stale.get(action.name, 0)
        if st.stale - last >= action.every:
            st.last_pivot_stale[action.name] = st.stale
            return True
        return False

    # -- observability -----------------------------------------------------------

    def _mirror(self, agent_id: str, global_count: int) -> None:
        if self.heartbeat_dir is None:
            return
        self.heartbeat_dir.mkdir(parents=True, exist_ok=True)
        st = self._state(agent_id)
        (self.heartbeat_dir / f"{agent_id}.json").write_text(json.dumps({
            "local_count": st.local_count,
            "stale": st.stale,
            "fired": st.fired,
        }, indent=2))
        (self.heartbeat_dir / "global.json").write_text(json.dumps({
            "eval_count": global_count,
            "fired": self._global_fired,
            "actions": [
                {"name": a.name, "every": a.every, "trigger": a.trigger, "scope": a.scope}
                for a in self.actions
            ],
        }, indent=2))

    def describe(self) -> str:
        lines = [f"{'action':<14} {'every':>5}  {'trigger':<9} scope"]
        for a in self.actions:
            lines.append(f"{a.name:<14} {a.every:>5}  {a.trigger:<9} {a.scope}")
        return "\n".join(lines)
