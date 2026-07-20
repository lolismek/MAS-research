#!/bin/bash
# v2 classic chain (piranha), launched by the orchestrator AFTER the G3 gate
# on the plain k=12 wave: board-family phase-1 (10 lanes) ∥ classic artifact
# builds (vanilla first, then per-arm parallel) -> board artifacts ->
# brackets + 7 classic arms phase-2 at 20 lanes (run_phase2.sh v2, logtag).
set -u
cd /tmp/aij2115/synchandoff
export PATH=$HOME/miniforge3/bin:$PATH
export UDOCKER_DIR=/tmp/aij2115/udocker SYNCHANDOFF_ENV=udocker
export SYNCHANDOFF_LLM_BASE=http://localhost:8744/m/v1
export SYNCHANDOFF_LLM_LOG=/tmp/aij2115/synchandoff/llm_calls_gpu.jsonl
PY=/tmp/aij2115/pyenv/bin/python

$PY - <<PYEOF
import json
cands = json.load(open("pilot_candidates.json"))
for i in range(10):
    json.dump(cands[i::10], open(f"/tmp/aij2115/board_shard_{i}.json", "w"))
PYEOF
echo "=== board wave + classic artifact builds start $(date +%H:%M:%S)"
for i in $(seq 0 9); do
  $PY -u phase1_runner.py --candidates /tmp/aij2115/board_shard_$i.json \
    --k 12 --family board > /tmp/aij2115/wave_board_$i.log 2>&1 &
done
(
  $PY -u build_artifacts.py --k 12 --arms vanilla > /tmp/aij2115/art_vanilla.log 2>&1
  echo "vanilla artifacts done $(date +%H:%M:%S)"
  for ARM in oracle ceiling full sop extract down; do
    $PY -u build_artifacts.py --k 12 --arms $ARM > /tmp/aij2115/art_$ARM.log 2>&1 &
  done
  wait
  echo "plain artifacts done $(date +%H:%M:%S)"
) &
wait
$PY -u build_artifacts.py --k 12 --arms board,board_inert > /tmp/aij2115/art_board.log 2>&1
echo "ARTIFACTS_DONE $(date +%H:%M:%S)"
/tmp/aij2115/run_phase2.sh 12 8 \
  floor,ceiling,oracle,vanilla,full,sop,down,extract,board,board_inert 20 all8b
echo CLASSIC_DONE
