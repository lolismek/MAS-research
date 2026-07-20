#!/bin/bash
# Usage: run_phase2_latent.sh <k> <m> <conditions-csv> [shards] [logtag]
# Same as run_phase2.sh but B's LLM path goes through the LATENT proxy
# (:8745 -> tunnel :8802 -> latent server on tigerfish GPU 1).
# NOTE: the latent server serializes GPU work (one request at a time), so
# keep shards small (1-2); more shards just queue.
set -e
K=$1; M=$2; CONDS=$3; SHARDS=${4:-1}; TAG=${5:-lat_k$1}
export PATH=$HOME/miniforge3/bin:$PATH
export UDOCKER_DIR=/tmp/aij2115/udocker SYNCHANDOFF_ENV=udocker
export SYNCHANDOFF_LLM_BASE=http://localhost:8745/m/v1
export SYNCHANDOFF_LLM_LOG=/tmp/aij2115/synchandoff/llm_calls_latent.jsonl
cd /tmp/aij2115/synchandoff
/tmp/aij2115/pyenv/bin/python - <<PYEOF
import json
cands = json.load(open("pilot_candidates.json"))
for i in range($SHARDS):
    json.dump(cands[i::$SHARDS], open(f"/tmp/aij2115/p2shard_${TAG}_{i}.json", "w"))
PYEOF
echo "=== latent phase2 k=$K m=$M conds=$CONDS shards=$SHARDS tag=$TAG start $(date +%H:%M:%S) ==="
for i in $(seq 0 $((SHARDS-1))); do
  /tmp/aij2115/pyenv/bin/python -u phase2_runner.py --candidates /tmp/aij2115/p2shard_${TAG}_$i.json --k $K --m $M --conditions "$CONDS" > /tmp/aij2115/p2_${TAG}_$i.log 2>&1 &
done
wait
echo "=== latent phase2 tag=$TAG done $(date +%H:%M:%S) ==="
grep -hiE "Traceback|ERROR" /tmp/aij2115/p2_${TAG}_*.log | sort | uniq -c | sort -rn | head -3 || true
