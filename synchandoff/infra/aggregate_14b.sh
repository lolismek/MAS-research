#!/bin/bash
# Aggregate the v2 (Qwen3-14B fallback; PLAN_V2 said results/8b — renamed to
# results/14b to reflect the executed model) results:
#   results/14b/classic_k12_m8.txt  brackets + 7 classic arms
#   results/14b/latent_k12_m8.txt   latent arms + timing
#   results/14b/probe_val.txt       belief-strength probe validation
#   results/14b/capacity_ledgers.json  per-arm slot/bit ledgers from artifact aux
set -u
cd /tmp/aij2115/synchandoff
PY=/tmp/aij2115/pyenv/bin/python
mkdir -p results/14b
$PY pilot_report.py > results/14b/classic_k12_m8.txt 2>&1
$PY latent/aggregate_progress.py > /dev/null 2>&1 || true
cp results/latent_progress.txt results/14b/latent_k12_m8.txt 2>/dev/null || true
{ echo "=== belief-strength probe validation (train.py output)";
  tail -20 /tmp/aij2115/probe_train.log 2>/dev/null;
  echo; echo "=== probes.json summary";
  $PY - <<'PYEOF'
import json
try:
    p = json.load(open("latent/probe/probes.json"))["belief_strength"]
    print({k: p[k] for k in ("layer", "val_acc", "val_auc", "entropy_corr",
                             "base_rate", "n", "val_acc_by_domain")})
except Exception as e:
    print("probes.json unavailable:", e)
PYEOF
} > results/14b/probe_val.txt
$PY - <<'PYEOF'
import glob, json
out = {}
for f in glob.glob("artifacts/*/plain_k12/l*.json"):
    aux = json.load(open(f))
    arm = f.rsplit("/", 1)[1][:-5]
    d = out.setdefault(arm, {"n": 0, "slot_units": set(), "total_bytes": []})
    d["n"] += 1
    d["slot_units"].add(str(aux.get("slot_unit")))
    b = (aux.get("bit_ledger") or {}).get("total_bytes")
    if b:
        d["total_bytes"].append(b)
for arm, d in out.items():
    d["slot_units"] = sorted(d["slot_units"])
    tb = d.pop("total_bytes")
    d["mean_total_bytes"] = int(sum(tb) / len(tb)) if tb else None
json.dump(out, open("results/14b/capacity_ledgers.json", "w"), indent=1)
print("capacity ledgers:", json.dumps(out, indent=1)[:400])
PYEOF
echo AGGREGATED
