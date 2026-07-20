#!/bin/bash
# Chain: phase-1 TRAINING wave (already running) -> activation capture ->
# probe training. Emits CAPTURE_DONE / TRAIN_DONE markers; the lprobe
# artifact build + vLLM-side waves are launched by the orchestrator after
# checking the CV numbers in probe_train.log.
cd /tmp/aij2115/synchandoff
export PATH=$HOME/miniforge3/bin:$PATH
while pgrep -u aij2115 -f "[p]hase1_runner.py --candidates /tmp/aij2115/train_shard" > /dev/null; do
  sleep 120
done
echo "train wave finished $(date +%H:%M:%S)"
export SYNCHANDOFF_LATENT_BASE=http://localhost:${LATENT_CAPTURE_PORT:-8802}
/tmp/aij2115/pyenv/bin/python -u -m latent.probe.capture \
  --candidates latent/probe/train_candidates.json --k 12 \
  > /tmp/aij2115/probe_capture.log 2>&1
echo CAPTURE_DONE
/tmp/aij2115/pyenv/bin/python -u -m latent.probe.train > /tmp/aij2115/probe_train.log 2>&1
echo TRAIN_DONE
