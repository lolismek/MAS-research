#!/bin/bash
# Usage: run_phase2.sh <k> <m> <conditions-csv> [shards] [logtag]
# logtag keeps the shard + log files of concurrent waves separate
# (e.g. board wave and plain wave both at k=12).
set -e
K=$1; M=$2; CONDS=$3; SHARDS=${4:-6}; TAG=${5:-k$1}
export PATH=$HOME/miniforge3/bin:$PATH
export UDOCKER_DIR=/tmp/aij2115/udocker SYNCHANDOFF_ENV=udocker
export SYNCHANDOFF_LLM_BASE=http://localhost:8744/m/v1
export SYNCHANDOFF_LLM_LOG=/tmp/aij2115/synchandoff/llm_calls_gpu.jsonl
cd /tmp/aij2115/synchandoff
/tmp/aij2115/pyenv/bin/python - <<PYEOF
import json
cands = json.load(open("pilot_candidates.json"))
for i in range($SHARDS):
    json.dump(cands[i::$SHARDS], open(f"/tmp/aij2115/p2shard_${TAG}_{i}.json", "w"))
PYEOF
echo "=== phase2 k=$K m=$M conds=$CONDS shards=$SHARDS tag=$TAG start $(date +%H:%M:%S) ==="
for i in $(seq 0 $((SHARDS-1))); do
  /tmp/aij2115/pyenv/bin/python -u phase2_runner.py --candidates /tmp/aij2115/p2shard_${TAG}_$i.json --k $K --m $M --conditions "$CONDS" > /tmp/aij2115/p2_${TAG}_$i.log 2>&1 &
done
wait
echo "=== phase2 tag=$TAG done $(date +%H:%M:%S) ==="
grep -hiE "Traceback|ERROR" /tmp/aij2115/p2_${TAG}_*.log | sort | uniq -c | sort -rn | head -3 || true
