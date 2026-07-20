"""G1 part B: Qwen acts coherently in the env through the minimal tool loop.

Runs a floor-bracket-style episode (no handoff artifact) on one instance with
a small tool budget, then scores it with the harness's own pytest run + git
diff. Pass condition is MECHANICAL (G1): the model emits well-formed tool
calls, observations flow back, trajectory serializes, tests execute. Whether
it actually fixes the repo is G2's question.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import instances as I
from harness.agent import run_agent
from harness.env import InstanceEnv, tests_pass
from harness.prompts import build_prompts

BUDGET = 10
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "smoke", "out")


def main():
    callee = I.load_instances("callee")
    inst = [i for i in callee if i["instance_id"].startswith("10_flask")][0]
    iid = inst["instance_id"]
    print(f"instance: {iid}")

    env = InstanceEnv(inst)
    try:
        env.start()
        env.setup_out_of_sync()
        system, user = build_prompts(inst, BUDGET, phase="solo")
        result = run_agent(env, system, user, tool_budget=BUDGET, tag=f"g1smoke:{iid}")

        summary, raw = env.run_tests()
        gold = I.parse_summary(inst["gold_summary"])
        diff = env.agent_diff()
        result["post_test_summary"] = summary
        result["success"] = tests_pass(summary, gold)
        result["agent_diff_files"] = diff["files"]

        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, "g1_agent_smoke.json"), "w") as f:
            json.dump(result, f, indent=1)

        print(f"\nstop_reason={result['stop_reason']} tool_calls={result['tool_calls_used']}")
        print(f"usage={result['usage']}")
        print(f"post-episode tests: {summary}")
        print(f"success={result['success']} files_touched={diff['files']}")
        print("\n--- action trace ---")
        for ev in result["events"]:
            if ev["type"] == "tool":
                arg = ev["arguments"].get("command") or ev["arguments"].get("path") or ""
                print(f"  {ev['name']}: {str(arg)[:110]}")
            elif ev["type"] == "assistant" and not ev["tool_calls"] and ev["content"]:
                print(f"  [final] {ev['content'][:200]}")
    finally:
        env.stop()


if __name__ == "__main__":
    main()
