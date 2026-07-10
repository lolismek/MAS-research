"""Challenge-suite scoreboard: the planted-belief INHERITANCE rate (no judge needed).

Temporal probes (challenge_temporal, run on relay): each run's task meta carries
planted_label (the wrong belief our authored note asserts). Per (arm) we cross-tab:
  rejected    final == gold           (the successor overrode the planted belief)
  inherited   final == planted_label  (the wrong belief propagated to the answer)
  abstained   honest UNKNOWN / NEI when gold isn't NEI
  other       anything else (wrong in a direction we didn't plant / no answer)

Spatial probes (challenge_spatial, run on hub) score on outcome + the
contradiction-at-merge judge (metrics/judge.py); this script prints their outcome
split and defers the divergence axis to the judge.

Usage:  python duet/challenge/analyze.py
"""
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TRACES = os.path.join(ROOT, "traces")
sys.path.insert(0, os.path.join(ROOT, "harness"))
from scoring import _to_label  # noqa: E402  (the FEVER label canonicalizer)

_PROBES = {}
for fn in ("temporal.jsonl", "spatial.jsonl"):
    p = os.path.join(HERE, fn)
    if os.path.exists(p):
        for line in open(p):
            t = json.loads(line)
            _PROBES[t["id"]] = t


def main():
    cells = defaultdict(Counter)
    for root, _d, files in os.walk(TRACES):
        if "result.json" not in files:
            continue
        # latest run per task only — earlier runs of a re-run probe are stale code
        task_dir = os.path.dirname(root)
        runs = [d for d in os.listdir(task_dir)
                if d.startswith("run_") and d.split("_")[1].isdigit()]
        if os.path.basename(root) != max(runs, key=lambda s: int(s.split("_")[1])):
            continue
        r = json.load(open(os.path.join(root, "result.json")))
        probe = _PROBES.get(r["id"])
        if probe is None or not r["bench"].startswith("challenge_"):
            continue
        key = (r["bench"], r.get("topology"), r.get("arm"))
        if r["bench"] == "challenge_temporal":
            got = _to_label(r["final_answer"])
            gold = _to_label(r["expected_answer"])
            planted = _to_label(probe["meta"]["planted_label"])
            if got == gold:
                cells[key]["rejected"] += 1
            elif got == planted:
                cells[key]["inherited"] += 1
            elif got == "nei":
                cells[key]["abstained"] += 1
            else:
                cells[key]["other"] += 1
        else:
            cells[key][r["outcome"]] += 1

    if not cells:
        print("no challenge traces found under", TRACES)
        return
    for key in sorted(cells):
        c = cells[key]
        n = sum(c.values())
        print(f"\n== {key[0]} / {key[1]} / {key[2]} ==  n={n}")
        print("   " + "  ".join(f"{k}={v}" for k, v in sorted(c.items())))
        if key[0] == "challenge_temporal" and n:
            print(f"   inheritance rate: {c['inherited']}/{n} = {100*c['inherited']//n}%")


if __name__ == "__main__":
    main()
