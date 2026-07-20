"""G1 part A: instance-env validation, no LLM involved.

For each smoke instance: build the out-of-sync state -> tests must fail the
way original_summary recorded; restore gold -> tests must pass the way
gold_summary recorded. Exact count match on (passed, failed, error).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness import instances as I
from harness.env import InstanceEnv, summaries_match


def check(instance):
    iid = instance["instance_id"]
    print(f"\n=== {iid}")
    print(f"    image: {I.image_for(instance)}")
    env = InstanceEnv(instance)
    ok = True
    try:
        env.start()
        env.setup_out_of_sync()
        got, raw = env.run_tests()
        want = I.parse_summary(instance["original_summary"])
        m = summaries_match(got, want)
        print(f"    out-of-sync: got {got} | want {want} | {'MATCH' if m else 'MISMATCH'}")
        if not m:
            print("    --- tail of pytest output ---")
            print("    " + "\n    ".join(raw[-1500:].split("\n")))
            ok = False

        env.restore_gold()
        got, raw = env.run_tests()
        want = I.parse_summary(instance["gold_summary"])
        m = summaries_match(got, want)
        print(f"    gold:        got {got} | want {want} | {'MATCH' if m else 'MISMATCH'}")
        if not m:
            print("    --- tail of pytest output ---")
            print("    " + "\n    ".join(raw[-1500:].split("\n")))
            ok = False
    finally:
        env.stop()
    return ok


if __name__ == "__main__":
    callee = I.load_instances("callee")
    # two different repos: fastapi (verified image) + flask (small, pure python)
    smoke = [callee[0]] + [i for i in callee if i["instance_id"].startswith("10_flask")][:1]
    results = {i["instance_id"]: check(i) for i in smoke}
    print("\n=== G1 env check:", "PASS" if all(results.values()) else "FAIL")
    for k, v in results.items():
        print(f"    {'ok ' if v else 'BAD'} {k}")
    sys.exit(0 if all(results.values()) else 1)
