"""PDDL -> tasks.jsonl (interactive planning environments via pddlgym).

Unlike the QA benches, the 'answer' here is the ENV STATE: agents drive a stateful
pddlgym world with the pddl_observe / pddl_actions / pddl_step tools, and scoring
reads goal-reached / progress off the ground-literal sets (scoring.classify_pddl_outcome,
camel/harness/pddl_env.py). This is the belief-state testbed — obs.literals is exactly
what a shared belief board would hold, so vanilla vs belief_board measures the
wrong_confident (state-divergence) rate.

answer_type="pddl"; tool_profile="pddl". NEEDS pddlgym -> run in the camel_pddl env:
  conda run -n camel_pddl python benchmarks/pddl/prep.py
  PDDL_PER_DOMAIN=4 conda run -n camel_pddl python benchmarks/pddl/prep.py   # smaller
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import write_tasks  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# (env_id, human domain name, default #problems, per-task step budget). Classic,
# text-renderable domains; skip grid/spatial ones (Sokoban) that render poorly.
DOMAINS = [
    ("PDDLEnvBlocks-v0",  "Blocksworld", 10, 40),
    ("PDDLEnvGripper-v0", "Gripper",     10, 40),
    ("PDDLEnvFerry-v0",   "Ferry",       10, 40),
    ("PDDLEnvHanoi-v0",   "Hanoi",        6, 60),
]
PER_DOMAIN = int(os.environ.get("PDDL_PER_DOMAIN", "0"))   # 0 = use per-domain defaults

INSTR = (
    "You are an agent operating in an interactive {domain} planning environment.\n"
    "The world has a state of true facts and a goal (a set of facts that must ALL "
    "hold at once). Solve it by ACTING, using these tools:\n"
    "  - pddl_observe: see the current true facts, the goal, and your progress.\n"
    "  - pddl_actions: list the actions valid in the current state.\n"
    "  - pddl_step: apply ONE action (e.g. 'pickup(a)' or 'stack(a,b)').\n"
    "Begin by observing. Then plan and act one step at a time, re-observing as needed, "
    "until every goal fact holds. When the environment reports GOAL REACHED, reply "
    "FINAL ANSWER: DONE. If you become certain the goal is unreachable, reply "
    "FINAL ANSWER: UNKNOWN.")


def build():
    import pddlgym  # camel_pddl env
    tasks, i = [], 0
    for env_id, domain, n_default, max_steps in DOMAINS:
        n = PER_DOMAIN or n_default
        try:
            env = pddlgym.make(env_id)
        except Exception as e:
            print(f"skip {env_id}: {e!r}")
            continue
        n_problems = len(getattr(env, "problems", []) or [])
        take = min(n, n_problems) if n_problems else n
        for idx in range(take):
            tasks.append(dict(
                id=f"pddl_{i:03d}", bench="pddl",
                question=INSTR.format(domain=domain),
                expected_answer="GOAL_REACHED",   # placeholder; pddl scoring reads env state
                answer_type="pddl", tool_profile="pddl",
                meta=dict(env_id=env_id, problem_index=idx, domain=domain,
                          max_steps=max_steps)))
            i += 1
        print(f"{domain}: {take} problems (of {n_problems} available)")
    write_tasks(os.path.join(HERE, "tasks.jsonl"), tasks)


if __name__ == "__main__":
    build()
