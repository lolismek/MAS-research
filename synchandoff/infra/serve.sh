#!/bin/bash
# vLLM serving of the SyncHandoff backend model on GPUs 0,1 (TP2).
# HOME is faked into /tmp: the real home is over its NFS quota, and several
# libs (flashinfer, torch inductor, vllm) write ~/.cache regardless of XDG.
export HOME=/tmp/aij2115/fakehome
export PATH=/tmp/aij2115/vllmenv/bin:$PATH
export CUDA_VISIBLE_DEVICES=2,3
export XDG_CACHE_HOME=/tmp/aij2115/cache
export HF_HOME=/tmp/aij2115/cache/hf
export VLLM_CACHE_ROOT=/tmp/aij2115/cache/vllm
export TRITON_CACHE_DIR=/tmp/aij2115/cache/triton
mkdir -p /tmp/aij2115/fakehome /tmp/aij2115/cache/vllm /tmp/aij2115/cache/hf /tmp/aij2115/cache/triton
exec /tmp/aij2115/vllmenv/bin/vllm serve /tmp/aij2115/models/qwen36-awq --served-model-name Qwen/Qwen3.6-35B-A3B --tensor-parallel-size 2 --max-model-len 65536 --gpu-memory-utilization 0.90 --host 0.0.0.0 --port 8801 --enable-auto-tool-choice --tool-call-parser hermes
