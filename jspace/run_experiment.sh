#!/bin/bash
# E2-mini batch entry point (runs ON tigerfish, everything localhost).
# Usage: bash run_experiment.sh <name> <limit> <arms> [workers]
#   smoke: bash run_experiment.sh smoke 2 note,note_jspace 2
#   full:  bash run_experiment.sh full 40 note,note_jspace 8
source ~/miniforge3/etc/profile.d/conda.sh
conda activate /tmp/aij2115_scratch/envs/jspace
cd "$(dirname "$0")"

export PROXY_URL="http://127.0.0.1:8397/v1"          # vLLM direct (no /m/tag route)
export JSPACE_URL="http://127.0.0.1:8398"
export CHAINLOSS_TOTAL_BUDGET=16000                   # E2-mini spec: fixed 16k/run
export CHAINLOSS_BUDGET_USD=0                         # self-hosted: USD cap off
export CHAINLOSS_PREFILL_RATE=0
export CHAINLOSS_SAMPLE_RATE=0
# Qwen3.5 hybrid thinking OFF, deterministically, on every call:
export CHAINLOSS_EXTRA_BODY='{"chat_template_kwargs":{"enable_thinking":false}}'

python harness/run_batch.py --tasks fanoutqa.jsonl --limit "${2:-2}" --ns 2 \
    --arms "${3:-note,note_jspace}" --workers "${4:-8}" --name "${1:-smoke}"
