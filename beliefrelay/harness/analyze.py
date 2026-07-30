"""Accuracy per arm from results/grid.jsonl -> printed table (+ optional REPORT block).

Sample-level accuracy with Wilson 95% CIs, task-level means, and per-task paired
deltas between arms (same tasks, same k — the paired view is the sensitive one).
"""
import json
import math
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRID = os.path.join(ROOT, "results", "grid.jsonl")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def main():
    recs = [json.loads(l) for l in open(GRID)]
    by_arm = defaultdict(list)
    by_arm_task = defaultdict(lambda: defaultdict(list))
    for r in recs:
        by_arm[r["arm"]].append(r["correct"])
        by_arm_task[r["arm"]][r["task_id"]].append(r["correct"])

    print(f"{'arm':8s} {'n':>4s} {'acc':>6s}  {'95% CI':>15s}  task-level")
    for arm in ("none", "homo", "probe"):
        if arm not in by_arm:
            continue
        v = by_arm[arm]
        p, lo, hi = wilson(sum(v), len(v))
        tl = [sum(x) / len(x) for x in by_arm_task[arm].values()]
        print(f"{arm:8s} {len(v):4d} {p:6.3f}  [{lo:.3f}, {hi:.3f}]  "
              f"{sum(tl)/len(tl):.3f} over {len(tl)} tasks")

    arms = [a for a in ("none", "homo", "probe") if a in by_arm]
    for i in range(len(arms)):
        for j in range(i + 1, len(arms)):
            a, b = arms[i], arms[j]
            common = set(by_arm_task[a]) & set(by_arm_task[b])
            deltas = [sum(by_arm_task[b][t]) / len(by_arm_task[b][t])
                      - sum(by_arm_task[a][t]) / len(by_arm_task[a][t])
                      for t in common]
            if not deltas:
                continue
            m = sum(deltas) / len(deltas)
            sd = (sum((d - m) ** 2 for d in deltas) / max(1, len(deltas) - 1)) ** 0.5
            se = sd / math.sqrt(len(deltas))
            print(f"paired {b} - {a}: {m:+.3f} (SE {se:.3f}, {len(deltas)} tasks) "
                  f"-> {'sig' if abs(m) > 1.96 * se else 'ns'} at ~95%")

    # truncation / degeneration check
    trunc = sum(1 for r in recs for t in r["transcript"] if t.get("finish") == "length")
    print(f"\nlength-truncated agent turns: {trunc} / {sum(len(r['transcript']) for r in recs)}")


if __name__ == "__main__":
    main()
