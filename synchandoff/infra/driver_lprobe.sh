#!/bin/bash
# v2 chain for the L-PROBE trio once the belief-strength probe is trained
# (driver_probe_v2.sh writes latent/probe/probes.json): build lprobe /
# lprobe_randsel / lprobe_shuffled artifacts for all 30 pilot instances
# (trace capture via the latent server + summarizer via vLLM :8744), then
# run their B-side waves through the FAST vLLM :8744 stack at 10 lanes —
# these are TEXT artifacts within W; no latent injection at B time
# (licensed by the greedy parity check). A-unsolved slice first.
set -u
cd /tmp/aij2115/synchandoff
export PATH=$HOME/miniforge3/bin:$PATH
export UDOCKER_DIR=/tmp/aij2115/udocker SYNCHANDOFF_ENV=udocker
export SYNCHANDOFF_LLM_LOG=/tmp/aij2115/synchandoff/llm_calls_gpu.jsonl
while [ ! -s latent/probe/probes.json ]; do sleep 120; done
echo "probes.json present $(date +%H:%M:%S)"
export SYNCHANDOFF_LATENT_BASE=http://localhost:${LATENT_CAPTURE_PORT:-8803}
export SYNCHANDOFF_LLM_BASE=http://localhost:8744/m/v1
ALL_IDS=$(/tmp/aij2115/pyenv/bin/python -c "import json;print(','.join(c['instance_id'] for c in json.load(open('/tmp/aij2115/aunsolved.json'))+json.load(open('/tmp/aij2115/asolved.json'))))")
/tmp/aij2115/pyenv/bin/python -u build_artifacts.py --k 12 \
  --arms lprobe,lprobe_randsel,lprobe_shuffled --instances "$ALL_IDS" \
  > /tmp/aij2115/build_lprobe.log 2>&1
echo LPROBE_ARTIFACTS_DONE
for SLICE in aunsolved asolved; do
  SH=10
  /tmp/aij2115/pyenv/bin/python - <<PYEOF
import json
c = json.load(open("/tmp/aij2115/${SLICE}.json"))
for i in range($SH):
    json.dump(c[i::$SH], open(f"/tmp/aij2115/lp_${SLICE}_{i}.json", "w"))
PYEOF
  echo "=== lprobe waves slice=$SLICE start $(date +%H:%M:%S)"
  for i in $(seq 0 $((SH-1))); do
    /tmp/aij2115/pyenv/bin/python -u phase2_runner.py \
      --candidates /tmp/aij2115/lp_${SLICE}_$i.json --k 12 --m 8 \
      --conditions lprobe,lprobe_randsel,lprobe_shuffled \
      > /tmp/aij2115/lp_${SLICE}_$i.log 2>&1 &
  done
  wait
  echo "=== lprobe waves slice=$SLICE DONE $(date +%H:%M:%S)"
done
echo LPROBE_ALL_DONE
