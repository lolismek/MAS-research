#!/bin/bash
# Qwen3-14B fallback stack (PLAN_V2 §Sanity): vLLM on ONE GPU, port 8804 —
# same port/proxies/tunnels as the 8B stack it replaces. Thinking disabled
# via the baked template (build with make_nothink.py from the 14B snapshot).
export HOME=/tmp/aij2115/fakehome
export PATH=/tmp/aij2115/vllmenv/bin:$PATH
# TP2 on GPUs 0,3: one 40G GPU fits the 14B weights but not the 65536-window
# KV pool (needs 10 GiB, 6.4 available); TP2 splits weights and doubles KV.
export CUDA_VISIBLE_DEVICES=${VLLM14B_GPU:-0,3}
export XDG_CACHE_HOME=/tmp/aij2115/cache
export HF_HOME=/tmp/aij2115/cache/hf
export VLLM_CACHE_ROOT=/tmp/aij2115/cache/vllm
export TRITON_CACHE_DIR=/tmp/aij2115/cache/triton
# THINKING ON (v2 deviation, 2026-07-20): no-think Qwen3 (8B and 14B both)
# degenerates in the agentic loop — empty assistant turns, tool-call
# thrashing, G3 solved 0%. Every calibrated run of this harness (v1 35B,
# duet) ran thinking-ON with the proxy's think-strip. YaRN x2 (Qwen official
# recipe: original 32768) gives the 65536 window that thinking + 34k-token
# read-heavy prompts + KV-offset B positions need.
SNAP=$(ls -d /tmp/aij2115/cache/hf/hub/models--Qwen--Qwen3-14B/snapshots/*/ | head -1)
exec /tmp/aij2115/vllmenv/bin/vllm serve "$SNAP" --served-model-name Qwen/Qwen3-14B \
  --tensor-parallel-size 2 \
  --max-model-len 65536 --gpu-memory-utilization 0.90 --host 0.0.0.0 \
  --hf-overrides "{\"rope_parameters\":{\"rope_type\":\"yarn\",\"rope_theta\":1000000,\"factor\":2.0,\"original_max_position_embeddings\":32768}}" \
  --port ${VLLM14B_PORT:-8804} --enable-auto-tool-choice --tool-call-parser hermes
