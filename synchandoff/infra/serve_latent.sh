#!/bin/bash
# Latent server on tigerfish (HF transformers, custom AWQ-MoE loader), one GPU.
# GPU 1 is the free one as of 2026-07-20 (GPU 0 = horvitz's job, GPUs 2,3 =
# the text-arm vLLM — NEVER touch those). Override with LATENT_GPU / LATENT_PORT.
# Code lives in /tmp/aij2115/latent (scp'd from synchandoff/latent/).
export HOME=/tmp/aij2115/fakehome
export XDG_CACHE_HOME=/tmp/aij2115/cache
export HF_HOME=/tmp/aij2115/cache/hf
export TRITON_CACHE_DIR=/tmp/aij2115/cache/triton
export CUDA_VISIBLE_DEVICES=${LATENT_GPU:-1}
cd /tmp/aij2115/latent
exec /tmp/aij2115/latentenv/bin/python -u server.py --port ${LATENT_PORT:-8802}
