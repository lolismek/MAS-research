"""Smoke sweep: seeds × (7 arms + floor + ceiling), parallel episodes.

Usage:
  run_smoke.py [--seeds a,b] [--arms x,y|all] [--turns N] [--workers K] [--out DIR]

Defaults: 2 seeds × all arms + floor/ceiling, 6 turns, 7 workers,
traces under beliefdial/traces/smoke/<arm>/<seed>/run_1/. Prints a per-arm
table (leaky lift over floor is the headline) and total self-metered cost.
The FULL grid is NOT run from here — smoke only (spend cap discipline).
"""
import argparse
import json
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from arms import ARMS
from run_task import load_seed, run_episode

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
DEFAULT_SEEDS = ["trip_advice", "contractor"]
ALL_ARMS = list(ARMS) + ["floor", "ceiling"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=",".join(DEFAULT_SEEDS))
    ap.add_argument("--arms", default="all")
    ap.add_argument("--turns", type=int, default=None)
    ap.add_argument("--workers", type=int, default=7)
    ap.add_argument("--out", default=os.path.join(ROOT, "traces", "smoke"))
    args = ap.parse_args()

    seeds = [load_seed(os.path.join(ROOT, "seeds", f"{s.strip()}.json"))
             for s in args.seeds.split(",")]
    arm_names = ALL_ARMS if args.arms == "all" else args.arms.split(",")

    jobs = [(seed, arm) for seed in seeds for arm in arm_names]
    results, failures = [], []

    def one(seed, arm):
        run_dir = os.path.join(args.out, arm, seed["id"], "run_1")
        return run_episode(seed, arm, run_dir, turns=args.turns)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(one, seed, arm): (seed["id"], arm)
                for seed, arm in jobs}
        for fut in as_completed(futs):
            sid, arm = futs[fut]
            try:
                res = fut.result()
                results.append(res)
                q = res["quiz"]
                print(f"done {sid:>14}/{arm:<11} leaky {q['leaky_correct']}/{q['leaky_n']} "
                      f"inert {q['inert_correct']}/{q['inert_n']} "
                      f"cant_tell {q['leaky_cant_tell'] + q['inert_cant_tell']} "
                      f"${res['usd']}", flush=True)
            except Exception:
                failures.append((sid, arm, traceback.format_exc()))
                print(f"FAIL {sid}/{arm}", flush=True)

    # ---- table: per arm, summed over seeds
    print("\n=== smoke summary (summed over seeds) ===")
    print(f"{'arm':<12} {'leaky':>7} {'inert':>7} {'cant_tell':>9} "
          f"{'probe_held':>10} {'leaked':>6} {'usd':>8}")
    total_usd = 0.0
    by_arm = {}
    for r in results:
        by_arm.setdefault(r["arm"], []).append(r)
    for arm in [a for a in (ALL_ARMS if args.arms == "all" else arm_names)
                if a in by_arm]:
        rs = by_arm[arm]
        lk = sum(r["quiz"]["leaky_correct"] for r in rs)
        lkn = sum(r["quiz"]["leaky_n"] for r in rs)
        inr = sum(r["quiz"]["inert_correct"] for r in rs)
        inn = sum(r["quiz"]["inert_n"] for r in rs)
        ct = sum(r["quiz"]["leaky_cant_tell"] + r["quiz"]["inert_cant_tell"] for r in rs)
        held = sum(r["probe"]["held"] for r in rs if r.get("probe"))
        heldn = sum(r["probe"]["n"] for r in rs if r.get("probe"))
        leaked = sum(r["leaks"]["leaked_slots"] for r in rs if r.get("leaks"))
        usd = sum(r["usd"] for r in rs)
        total_usd += usd
        probe_s = f"{held}/{heldn}" if heldn else "-"
        print(f"{arm:<12} {lk:>4}/{lkn:<2} {inr:>4}/{inn:<2} {ct:>9} "
              f"{probe_s:>10} {leaked:>6} {usd:>8.3f}")
    print(f"\ntotal episodes: {len(results)}  failures: {len(failures)}  "
          f"total usd: {total_usd:.3f}")
    for sid, arm, tb in failures:
        print(f"\n--- FAILURE {sid}/{arm}\n{tb}")

    with open(os.path.join(args.out, "summary.json"), "w") as f:
        json.dump({"results": results,
                   "failures": [(s, a) for s, a, _ in failures]}, f, indent=2)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
