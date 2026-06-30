"""Interactive PDDL environment (pddlgym) — a per-task, stateful, agent-callable
tool set. This is the ENV axis, orthogonal to the AddOn (arm) axis: a run is
(task x tool_profile x arm), and for a pddl task the env is threaded alongside the
addon so any arm (vanilla / belief_board) can drive the SAME world.

Why PDDL for the belief-state work: the state is `obs.literals`, a frozenset of
ground literals (`on(b,c)`, `holding(a)`) — exactly the shape a shared belief board
would hold. So vanilla vs belief_board on PDDL measures whether a shared literal-level
world model cuts the `wrong_confident` rate (the agent asserting it solved the task
while the true state shows the goal unmet = belief-state divergence).

pddlgym is imported LAZILY (only when an env is constructed) so the rest of the
harness still imports/runs without pddlgym installed (GAIA/MATH/PopQA/FEVER).
Validated against pddlgym + gym 0.26: reset() -> (obs, info); obs.literals /
obs.goal are literal sets; step() -> (obs, reward, done, truncated, info).
"""
import re

_TYPE = re.compile(r":[A-Za-z0-9_]+")        # the ':block' type tag in 'a:block'
_TOK = re.compile(r"[a-z0-9_]+")


def _fmt(lit):
    """Human/LLM-readable literal: drop the ':type' tags -> 'on(b, c)'."""
    return _TYPE.sub("", str(lit))


def _akey(s):
    """Order-preserving identity of an action for matching the model's free-text
    against the ground actions: predicate + arg names, types/parens/spaces dropped.
    So 'pickup(a:block)', 'pickup(a)' and 'pickup a' all key to ('pickup','a')."""
    return tuple(_TOK.findall(_TYPE.sub("", str(s).lower())))


class PddlEnv:
    """One pddlgym problem, instantiated from a task's `meta`:
        {env_id: "PDDLEnvBlocks-v0", problem_index: 0, domain: "Blocksworld", max_steps: 40}
    Exposes the three agent tools (observe/actions/step) via run_tool(), and
    goal_reached()/progress() for scoring."""

    def __init__(self, meta):
        import pddlgym  # lazy: keeps pddlgym out of the harness's import path
        self.env_id = meta["env_id"]
        self.problem_index = meta.get("problem_index", 0)
        self.domain = meta.get("domain", self.env_id)
        self.max_steps = int(meta.get("max_steps", 40))
        self.env = pddlgym.make(self.env_id)
        if self.problem_index is not None:
            self.env.fix_problem_index(self.problem_index)
        r = self.env.reset()
        self.obs = r[0] if isinstance(r, tuple) else r     # gym>=0.26 returns (obs, info)
        self.goal_lits = set(getattr(self.obs.goal, "literals", None) or [self.obs.goal])
        self.steps = 0
        self.invalid = 0
        self.done = False

    # --- state / scoring ---------------------------------------------------
    def _ground_actions(self):
        return sorted(self.env.action_space.all_ground_literals(self.obs), key=str)

    def goal_reached(self):
        return self.goal_lits.issubset(self.obs.literals)

    def progress(self):
        if not self.goal_lits:
            return 1.0
        return len(self.goal_lits & self.obs.literals) / len(self.goal_lits)

    def summary(self):
        return dict(env_id=self.env_id, problem_index=self.problem_index,
                    domain=self.domain, steps=self.steps, invalid=self.invalid,
                    goal_reached=self.goal_reached(), progress=round(self.progress(), 3))

    # --- the three agent-callable tools ------------------------------------
    def _status(self):
        hit = len(self.goal_lits & self.obs.literals)
        flag = " — GOAL REACHED" if self.goal_reached() else ""
        return f"Goal satisfied: {hit}/{len(self.goal_lits)} facts{flag}. Step {self.steps}/{self.max_steps}."

    def observe(self):
        facts = "\n".join("  " + _fmt(l) for l in sorted(self.obs.literals, key=str)) or "  (none)"
        goal = "\n".join("  " + _fmt(l) for l in sorted(self.goal_lits, key=str))
        return (f"Current state (true facts):\n{facts}\n\n"
                f"Goal (ALL must hold):\n{goal}\n\n{self._status()}")

    def actions(self):
        acts = self._ground_actions()
        listed = "\n".join("  " + _fmt(a) for a in acts) or "  (none applicable)"
        return (f"Valid actions now ({len(acts)}):\n{listed}\n\n"
                "Call pddl_step with exactly one of these (types optional, e.g. 'pickup(a)').")

    def step(self, arg):
        if self.done or self.steps >= self.max_steps:
            return f"No more steps allowed (budget {self.max_steps} used). {self._status()}"
        action = {_akey(a): a for a in self._ground_actions()}.get(_akey(arg))
        if action is None:
            self.invalid += 1
            sample = ", ".join(_fmt(a) for a in self._ground_actions()[:8])
            return (f"Invalid action {arg!r} — not applicable in the current state. "
                    f"Valid examples: {sample}. Call pddl_actions for the full list.")
        res = self.env.step(action)
        self.obs = res[0]                                  # (obs, reward, done, [trunc], info)
        self.steps += 1
        self.done = bool(res[2]) or self.goal_reached() or self.steps >= self.max_steps
        head = "GOAL REACHED. " if self.goal_reached() else f"Applied {_fmt(action)}. "
        return head + self.observe()

    def run_tool(self, name, arg):
        if name == "pddl_observe":
            return self.observe()
        if name == "pddl_actions":
            return self.actions()
        if name == "pddl_step":
            return self.step(arg)
        return f"ERROR: unknown env tool {name!r}"
