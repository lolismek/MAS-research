#!/bin/bash
# E2-mini serving on tigerfish GPU 3: vLLM OpenAI server for Qwen/Qwen3.5-4B,
# served-model-name gpt-4o so the chainloss-forked harness works unmodified.
# Memory capped at 0.55 so the HF lens-extraction service shares the same card.
source ~/miniforge3/etc/profile.d/conda.sh
conda activate /tmp/aij2115_scratch/envs/jspace
export HF_HOME=/tmp/aij2115_scratch/hf
export CUDA_VISIBLE_DEVICES=${JSPACE_GPU:-3}
exec vllm serve Qwen/Qwen3.5-4B \
    --served-model-name gpt-4o \
    --port 8397 \
    --gpu-memory-utilization 0.55 \
    --max-model-len 65536 \
    --max-num-seqs 16 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes
