"""Compute the A-solved / A-unsolved pilot slices from the NEW phase-1 metas
(family=plain, k=12, post_A_solved falsy => A-unsolved) and the 4 latent lane
files. Run on piranha after the phase-1 wave:
  /tmp/aij2115/pyenv/bin/python infra/make_slices.py
Writes /tmp/aij2115/{aunsolved,asolved}.json and /tmp/aij2115/lat_lane_[0-3].json
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

cands = json.load(open(os.path.join(HERE, "pilot_candidates.json")))
uns, sol, missing = [], [], []
for c in cands:
    mp = os.path.join(HERE, "phase1_frozen", c["instance_id"],
                      "plain_k12", "meta.json")
    if not os.path.exists(mp):
        missing.append(c["instance_id"])
        continue
    meta = json.load(open(mp))
    (sol if meta.get("post_A_solved") else uns).append(c)

json.dump(uns, open("/tmp/aij2115/aunsolved.json", "w"))
json.dump(sol, open("/tmp/aij2115/asolved.json", "w"))
for i in range(4):
    json.dump(uns[i::4], open(f"/tmp/aij2115/lat_lane_{i}.json", "w"))
print(f"A-unsolved {len(uns)}, A-solved {len(sol)}, missing_frozen {len(missing)}")
for m in missing:
    print("  missing:", m)
