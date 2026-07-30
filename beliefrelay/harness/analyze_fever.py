"""FEVER v3 analysis: accuracy per arm (Wilson + paired deltas, as analyze.py)
PLUS the directional readout — REFUTES-rate shift per belief flavor vs none.

Flavor map (prep_fever set order + rotations): homo arm task ordinal%3 ->
0 skeptic / 1 credulous / 2 neutral. Probe rotates flavor->position by ordinal,
so every relay has all three flavors; the probe readout is positional (which
flavor sat in the deciding seat 3: (2+r)%3... seat3 flavor = set index (2+r)%3).
"""
import json
import math
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAVORS = ["skeptic", "credulous", "neutral"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def main():
    grid = os.path.join(ROOT, "results",
                        sys.argv[1] if len(sys.argv) > 1 else "grid_fever.jsonl")
    pool = json.load(open(os.path.join(ROOT, "pool_fever.json")))
    ordinal = {p["task_id"]: i for i, p in enumerate(pool)}
    tasks = {json.loads(l)["id"]: json.loads(l)
             for l in open(os.path.join(ROOT, "data", "tasks_fever.jsonl"))}
    recs = [json.loads(l) for l in open(grid)]

    by_arm = defaultdict(list)
    by_arm_task = defaultdict(lambda: defaultdict(list))
    ref_rate = defaultdict(lambda: [0, 0])   # arm -> [n_refutes, n]
    for r in recs:
        by_arm[r["arm"]].append(r["correct"])
        by_arm_task[r["arm"]][r["task_id"]].append(r["correct"])
        ref_rate[r["arm"]][0] += r["answer"] == "REFUTES"
        ref_rate[r["arm"]][1] += 1

    print(f"{'arm':8s} {'n':>4s} {'acc':>6s}  {'95% CI':>15s}  REFUTES-rate")
    for arm in ("none", "homo", "probe"):
        v = by_arm.get(arm)
        if not v:
            continue
        p, lo, hi = wilson(sum(v), len(v))
        rr = ref_rate[arm]
        print(f"{arm:8s} {len(v):4d} {p:6.3f}  [{lo:.3f}, {hi:.3f}]  "
              f"{rr[0]/rr[1]:.3f}")

    arms = [a for a in ("none", "homo", "probe") if a in by_arm]
    for i in range(len(arms)):
        for j in range(i + 1, len(arms)):
            a, b = arms[i], arms[j]
            common = set(by_arm_task[a]) & set(by_arm_task[b])
            deltas = [sum(by_arm_task[b][t]) / len(by_arm_task[b][t])
                      - sum(by_arm_task[a][t]) / len(by_arm_task[a][t])
                      for t in common]
            m = sum(deltas) / len(deltas)
            sd = (sum((d - m) ** 2 for d in deltas) / max(1, len(deltas) - 1)) ** 0.5
            se = sd / math.sqrt(len(deltas))
            print(f"paired {b} - {a}: {m:+.3f} (SE {se:.3f}, {len(deltas)} tasks) "
                  f"-> {'sig' if abs(m) > 1.96 * se else 'ns'} at ~95%")

    # --- directional shift: homo flavor subsets vs the SAME tasks under none ---
    print("\nhomo flavor subsets (all 3 agents share that flavor), paired vs none:")
    print(f"{'flavor':10s} {'tasks':>5s} {'acc':>6s} {'REF-rate':>8s} "
          f"{'none-REF':>8s} {'shift':>7s}")
    ref_by = defaultdict(lambda: defaultdict(list))   # arm -> task -> [is_refutes]
    for r in recs:
        ref_by[r["arm"]][r["task_id"]].append(r["answer"] == "REFUTES")
    for fi, fl in enumerate(FLAVORS):
        tids = [t for t in by_arm_task.get("homo", {}) if ordinal[t] % 3 == fi]
        if not tids:
            continue
        acc = [x for t in tids for x in by_arm_task["homo"][t]]
        hr = [x for t in tids for x in ref_by["homo"][t]]
        nr = [x for t in tids for x in ref_by["none"].get(t, [])]
        shifts = [sum(ref_by["homo"][t]) / len(ref_by["homo"][t])
                  - sum(ref_by["none"][t]) / len(ref_by["none"][t])
                  for t in tids if t in ref_by["none"]]
        m = sum(shifts) / len(shifts)
        sd = (sum((d - m) ** 2 for d in shifts) / max(1, len(shifts) - 1)) ** 0.5
        se = sd / math.sqrt(len(shifts))
        print(f"{fl:10s} {len(tids):5d} {sum(acc)/len(acc):6.3f} "
              f"{sum(hr)/len(hr):8.3f} {sum(nr)/len(nr):8.3f} "
              f"{m:+7.3f} (SE {se:.3f})")

    # probe: flavor in the deciding seat (agent 3) = set index (2 + ordinal) % 3
    print("\nprobe by deciding-seat flavor (agent 3), REFUTES-rate:")
    for fi, fl in enumerate(FLAVORS):
        tids = [t for t in by_arm_task.get("probe", {})
                if (2 + ordinal[t]) % 3 == fi]
        if not tids:
            continue
        pr = [x for t in tids for x in ref_by["probe"][t]]
        nr = [x for t in tids for x in ref_by["none"].get(t, [])]
        print(f"  seat3={fl:10s} {len(tids):2d} tasks  probe-REF {sum(pr)/len(pr):.3f}"
              f"  none-REF {sum(nr)/len(nr):.3f}")

    mute = sum(1 for r in recs for t in r["transcript"]
               if (t["message"] or "").startswith("[the model could not"))
    trunc = sum(1 for r in recs for t in r["transcript"]
                if t.get("finish") == "length")
    n_turns = sum(len(r["transcript"]) for r in recs)
    print(f"\ntruncated turns {trunc}/{n_turns}, mute {mute}; "
          f"label balance: {sum(1 for t in tasks.values() if tasks and t['expected_answer']=='REFUTES')}R"
          f"/{len(tasks)} tasks")


if __name__ == "__main__":
    main()
