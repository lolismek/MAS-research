"""Aggregate duet traces -> a per-cell scoreboard, and the relay calibration view.

A cell = (topology, arm, bench). For each we print the outcome split (correct /
wrong_confident / abstained / no_answer), cost/time, and — for the relay — the
shifts-used distribution that the P0 calibration gate is defined on (PLAN: tune B so
vanilla uses >=2 shifts on ~70% of tasks). Latest run per task only.

Usage (from repo root):
  conda run -n autogen_gc python duet/harness/agg.py                 # all traces
  conda run -n autogen_gc python duet/harness/agg.py --topology relay --arm vanilla
"""
import json, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TRACES = os.path.join(os.path.dirname(HERE), "traces")
OUTCOMES = ["correct", "wrong_confident", "abstained", "no_answer"]


def latest_results(topology=None, arm=None):
    """Yield the latest run's result.json for each (topology,arm,bench,task)."""
    for root, _dirs, files in os.walk(TRACES):
        if "result.json" not in files or not os.path.basename(root).startswith("run_"):
            continue
        # keep only the highest run_N per task dir
        task_dir = os.path.dirname(root)
        runs = [d for d in os.listdir(task_dir)
                if d.startswith("run_") and d.split("_")[1].isdigit()]
        if os.path.basename(root) != max(runs, key=lambda s: int(s.split("_")[1])):
            continue
        r = json.load(open(os.path.join(root, "result.json")))
        if topology and r.get("topology") != topology:
            continue
        if arm and r.get("arm") != arm:
            continue
        yield r


def main():
    args = sys.argv[1:]
    topology = args[args.index("--topology") + 1] if "--topology" in args else None
    arm = args[args.index("--arm") + 1] if "--arm" in args else None

    cells = defaultdict(list)
    for r in latest_results(topology, arm):
        cells[(r.get("topology"), r.get("arm"), r.get("bench"))].append(r)
    if not cells:
        print("no traces found under", TRACES)
        return

    for key in sorted(cells):
        rs = cells[key]
        oc = Counter(r["outcome"] for r in rs)
        n = len(rs)
        cost = sum(r.get("cost_usd", 0) for r in rs)
        secs = sum(r.get("seconds", 0) for r in rs)
        shifts = Counter(r.get("shifts_used") for r in rs if r.get("shifts_used") is not None)
        multi = sum(v for s, v in shifts.items() if s and s >= 2)
        print(f"\n== {key[0]} / {key[1]} / {key[2]} ==  n={n}  ${cost:.3f}  {secs:.0f}s")
        print("   outcomes: " + "  ".join(f"{o}={oc.get(o,0)}" for o in OUTCOMES))
        if shifts:
            dist = " ".join(f"{s}sh×{shifts[s]}" for s in sorted(shifts))
            print(f"   shifts_used: {dist}   (>=2 shifts: {multi}/{n} = {100*multi//max(n,1)}%)")
        # per-task one-liners for eyeballing
        for r in sorted(rs, key=lambda x: x["id"]):
            extra = f" shifts={r.get('shifts_used')}" if r.get("shifts_used") else ""
            print(f"     {r['id']:<18} {r['outcome']:<15} final={r['final_answer'][:42]!r}"
                  f" exp={r['expected_answer'][:22]!r}{extra} ${r.get('cost_usd',0):.3f}")


if __name__ == "__main__":
    main()
