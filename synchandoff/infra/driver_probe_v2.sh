#!/bin/bash
# v2 probe chain (piranha): synthetic data-gen (vLLM :8804 tunnel) ->
# activation capture (latent server :8802/:8803) -> probe training.
# Emits GEN_DONE / CAPTURE_DONE / TRAIN_DONE markers. The lprobe artifact
# build + vLLM waves are launched by the orchestrator after checking the
# val-accuracy gate (>=0.75) in probe_train.log.
set -u
cd /tmp/aij2115/synchandoff
export PATH=$HOME/miniforge3/bin:$PATH
export SYNCHANDOFF_VLLM_BASE=${SYNCHANDOFF_VLLM_BASE:-http://localhost:8804/v1}
if [ ! -s latent/probe/synth_data.jsonl ]; then
  /tmp/aij2115/pyenv/bin/python -u -m latent.probe.gen_data \
    --n-batches ${GEN_BATCHES:-6} --workers ${GEN_WORKERS:-6} \
    > /tmp/aij2115/probe_gen.log 2>&1
fi
echo GEN_DONE
export SYNCHANDOFF_LATENT_BASE=http://localhost:${LATENT_CAPTURE_PORT:-8803}
# middle layers; 14B (Qwen3-14B) has 40 decoder layers -> 14/20/26 ~ depth
# 0.35/0.50/0.65 (the 8B/36-layer run used 12/18/24)
/tmp/aij2115/pyenv/bin/python -u -m latent.probe.capture_synth \
  --layers ${PROBE_LAYERS:-14,20,26} \
  > /tmp/aij2115/probe_capture.log 2>&1
echo CAPTURE_DONE
/tmp/aij2115/pyenv/bin/python -u -m latent.probe.train \
  > /tmp/aij2115/probe_train.log 2>&1
echo TRAIN_DONE
tail -8 /tmp/aij2115/probe_train.log
