#!/bin/bash
# E2-mini lens-extraction service (HF prefill + Jacobian lens @ L12) on GPU 3,
# sharing the card with vLLM (which is capped at 0.55 mem util).
source ~/miniforge3/etc/profile.d/conda.sh
conda activate /tmp/aij2115_scratch/envs/jspace
export HF_HOME=/tmp/aij2115_scratch/hf
export CUDA_VISIBLE_DEVICES=${JSPACE_GPU:-3}
cd "$(dirname "$0")/extractor"
exec python server.py
