#!/bin/bash
# v2 stack: vLLM serving Qwen/Qwen3-8B (dense bf16) on ONE GPU, port 8804.
# Thinking disabled via the baked chat template (infra/make_nothink.py);
# hermes tool parser as before. HOME faked into /tmp (NFS quota full).
export HOME=/tmp/aij2115/fakehome
export PATH=/tmp/aij2115/vllmenv/bin:$PATH
export CUDA_VISIBLE_DEVICES=${VLLM8B_GPU:-0}
export XDG_CACHE_HOME=/tmp/aij2115/cache
export HF_HOME=/tmp/aij2115/cache/hf
export VLLM_CACHE_ROOT=/tmp/aij2115/cache/vllm
export TRITON_CACHE_DIR=/tmp/aij2115/cache/triton
mkdir -p /tmp/aij2115/fakehome /tmp/aij2115/cache/vllm /tmp/aij2115/cache/hf /tmp/aij2115/cache/triton
SNAP=$(ls -d /tmp/aij2115/cache/hf/hub/models--Qwen--Qwen3-8B/snapshots/*/ | head -1)
exec /tmp/aij2115/vllmenv/bin/vllm serve "$SNAP" --served-model-name Qwen/Qwen3-8B \
  --max-model-len 40960 --gpu-memory-utilization 0.90 --host 0.0.0.0 \
  --port ${VLLM8B_PORT:-8804} --enable-auto-tool-choice --tool-call-parser hermes \
  --chat-template /tmp/aij2115/qwen3_nothink.jinja
