#!/bin/bash
# Arm-major latent phase-2 driver over the A-UNSOLVED pilot slice (14
# instances; only that slice discriminates — A-solved saturates SR).
# Per arm (coordinator's priority order): wait until every A-unsolved
# instance has the arm's artifact (built concurrently by build_artifacts
# against the two latent servers), then run 4 lanes — lanes 0,1 -> proxy
# :8745 (server :8802/GPU1), lanes 2,3 -> :8746 (:8803/GPU0). Two lanes per
# server is safe: the server frees each request's cache before returning and
# GPU_LOCK serializes compute, so lanes overlap GPU time with the (dominant)
# udocker test time instead of OOMing. Chains arms with no idle gaps.
# Usage: driver_latent_waves.sh   (lane files /tmp/aij2115/lat_lane_[0-3].json)
ARMS="lkv lkv_notekv lthought_pool lthought_rand lthought lkv_rand"
cd /tmp/aij2115/synchandoff
export PATH=$HOME/miniforge3/bin:$PATH
export UDOCKER_DIR=/tmp/aij2115/udocker SYNCHANDOFF_ENV=udocker
export SYNCHANDOFF_LLM_TIMEOUT=3900
export SYNCHANDOFF_LLM_LOG=/tmp/aij2115/synchandoff/llm_calls_latent.jsonl
UNS_IDS=$(/tmp/aij2115/pyenv/bin/python -c "import json;print(' '.join(c['instance_id'] for c in json.load(open('/tmp/aij2115/aunsolved.json'))))")
for ARM in $ARMS; do
  echo "=== arm $ARM: waiting for artifacts $(date +%H:%M:%S)"
  while true; do
    missing=0
    for iid in $UNS_IDS; do
      [ -s "artifacts/$iid/plain_k12/$ARM.txt" ] || missing=$((missing+1))
    done
    [ "$missing" -eq 0 ] && break
    sleep 60
  done
  echo "=== arm $ARM: launching 4 lanes $(date +%H:%M:%S)"
  for i in 0 1 2 3; do
    if [ "$i" -lt 2 ]; then BASE=http://localhost:8745/m/v1; else BASE=http://localhost:8746/m/v1; fi
    SYNCHANDOFF_LLM_BASE=$BASE /tmp/aij2115/pyenv/bin/python -u phase2_runner.py \
      --candidates /tmp/aij2115/lat_lane_$i.json --k 12 --m 8 --conditions "$ARM" \
      > /tmp/aij2115/lat_${ARM}_lane$i.log 2>&1 &
  done
  wait
  echo "=== arm $ARM DONE $(date +%H:%M:%S)"
done
echo ALL_LATENT_ARMS_DONE
