#!/bin/bash
# Qwen3-14B fallback stack (PLAN_V2 §Sanity): vLLM on ONE GPU, port 8804 —
# same port/proxies/tunnels as the 8B stack it replaces. Thinking disabled
# via the baked template (build with make_nothink.py from the 14B snapshot).
export HOME=/tmp/aij2115/fakehome
export PATH=/tmp/aij2115/vllmenv/bin:$PATH
export CUDA_VISIBLE_DEVICES=${VLLM14B_GPU:-0}
export XDG_CACHE_HOME=/tmp/aij2115/cache
export HF_HOME=/tmp/aij2115/cache/hf
export VLLM_CACHE_ROOT=/tmp/aij2115/cache/vllm
export TRITON_CACHE_DIR=/tmp/aij2115/cache/triton
SNAP=$(ls -d /tmp/aij2115/cache/hf/hub/models--Qwen--Qwen3-14B/snapshots/*/ | head -1)
exec /tmp/aij2115/vllmenv/bin/vllm serve "$SNAP" --served-model-name Qwen/Qwen3-14B \
  --max-model-len 40960 --gpu-memory-utilization 0.90 --host 0.0.0.0 \
  --port ${VLLM14B_PORT:-8804} --enable-auto-tool-choice --tool-call-parser hermes \
  --chat-template /tmp/aij2115/qwen3_nothink_14b.jinja
