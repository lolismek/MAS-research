#!/bin/bash
# Usage: run_wave_train.sh <k> [shards] [candidates]
# Phase-1 wave over the L-PROBE TRAINING split (repos disjoint from the
# pilot; default latent/probe/train_candidates.json). Same GPU path as
# run_wave.sh (proxy :8744 -> vLLM on tigerfish GPUs 2,3, $0).
set -e
K=$1; SHARDS=${2:-4}
CANDS=${3:-latent/probe/train_candidates.json}
export PATH=$HOME/miniforge3/bin:$PATH
export UDOCKER_DIR=/tmp/aij2115/udocker SYNCHANDOFF_ENV=udocker
export SYNCHANDOFF_LLM_BASE=http://localhost:8744/m/v1
export SYNCHANDOFF_LLM_LOG=/tmp/aij2115/synchandoff/llm_calls_gpu.jsonl
cd /tmp/aij2115/synchandoff
/tmp/aij2115/pyenv/bin/python - <<PYEOF
import json
cands = json.load(open("$CANDS"))
for i in range($SHARDS):
    json.dump(cands[i::$SHARDS], open(f"/tmp/aij2115/train_shard_{i}.json","w"))
PYEOF
echo "=== train wave k=$K start $(date +%H:%M:%S) ==="
for i in $(seq 0 $((SHARDS-1))); do
  /tmp/aij2115/pyenv/bin/python -u phase1_runner.py --candidates /tmp/aij2115/train_shard_$i.json --k $K > /tmp/aij2115/train_wave_${i}_k$K.log 2>&1 &
done
wait
echo "=== train wave k=$K done $(date +%H:%M:%S) ==="
grep -hc "frozen\]" /tmp/aij2115/train_wave_*_k$K.log | paste -sd+ | bc || true
grep -hiE "Traceback|ERROR" /tmp/aij2115/train_wave_*_k$K.log | sort | uniq -c | sort -rn | head -5 || true
