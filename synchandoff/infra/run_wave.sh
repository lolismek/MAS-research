#!/bin/bash
# Usage: run_wave.sh <k> [shards]  — phase-1 wave on the GPU backend.
# LLM path: harness -> local proxy :8744 -> tigerfish vLLM (AWQ, $0).
# Token log kept SEPARATE from the Tinker-priced llm_calls.jsonl.
set -e
K=$1; SHARDS=${2:-6}
export PATH=$HOME/miniforge3/bin:$PATH
export UDOCKER_DIR=/tmp/aij2115/udocker SYNCHANDOFF_ENV=udocker
export SYNCHANDOFF_LLM_BASE=http://localhost:8744/m/v1
export SYNCHANDOFF_LLM_LOG=/tmp/aij2115/synchandoff/llm_calls_gpu.jsonl
cd /tmp/aij2115/synchandoff
/tmp/aij2115/pyenv/bin/python - <<PYEOF
import json
cands = json.load(open("pilot_candidates.json"))
for i in range($SHARDS):
    json.dump(cands[i::$SHARDS], open(f"/tmp/aij2115/wave_shard_{i}.json","w"))
PYEOF
echo "=== wave k=$K start $(date +%H:%M:%S) ==="
for i in $(seq 0 $((SHARDS-1))); do
  /tmp/aij2115/pyenv/bin/python -u phase1_runner.py --candidates /tmp/aij2115/wave_shard_$i.json --k $K > /tmp/aij2115/wave_${i}_k$K.log 2>&1 &
done
wait
echo "=== wave k=$K done $(date +%H:%M:%S) ==="
grep -hc "frozen\]" /tmp/aij2115/wave_*_k$K.log | paste -sd+ | bc
grep -hiE "Traceback|ERROR" /tmp/aij2115/wave_*_k$K.log | sort | uniq -c | sort -rn | head -3 || true
