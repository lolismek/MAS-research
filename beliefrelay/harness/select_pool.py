"""Pick the experiment pool from prescreen.jsonl: tasks in the 0-50% single-agent
solve band (difficulty calibrated to THIS model, not the human level label).

  conda run -n base python beliefrelay/harness/select_pool.py [--n 50]

Writes pool.json: [{task_id, screen_rate}, ...] sorted by task_id. Within the band,
prefers tasks with rate > 0 (some signal the task is solvable — pure-0 tasks risk
floor effects), then fills from the 0s if needed.
"""
import argparse
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREEN = os.path.join(ROOT, "results", "prescreen.jsonl")
POOL = os.path.join(ROOT, "pool.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--band-max", type=float, default=0.5)
    args = ap.parse_args()

    hits = defaultdict(list)
    fins = defaultdict(list)
    for line in open(SCREEN):
        r = json.loads(line)
        hits[r["task_id"]].append(r["correct"])
        fins[r["task_id"]].append(r["finish"])
    rates = {t: sum(v) / len(v) for t, v in hits.items()}
    # Hard-but-answerable only: a task ALL of whose samples died at the token cap
    # never produced an answer at all — that's budget-bound, not hard. Require at
    # least one completed (finish=stop) sample to be eligible.
    band = [(t, r) for t, r in rates.items()
            if r <= args.band_max and any(f == "stop" for f in fins[t])]
    partial = sorted([x for x in band if x[1] > 0], key=lambda x: x[0])
    zero = sorted([x for x in band if x[1] == 0], key=lambda x: x[0])
    chosen = (partial + zero)[:args.n]
    chosen.sort(key=lambda x: x[0])
    json.dump([dict(task_id=t, screen_rate=r) for t, r in chosen],
              open(POOL, "w"), indent=1)
    dist = defaultdict(int)
    for _, r in chosen:
        dist[r] += 1
    print(f"screened {len(rates)} tasks; band(<= {args.band_max}) = {len(band)}; "
          f"pool = {len(chosen)}")
    print("pool screen-rate distribution:", dict(sorted(dist.items())))
    print(f"pool mean screen rate: {sum(r for _, r in chosen)/len(chosen):.3f}")


if __name__ == "__main__":
    main()
