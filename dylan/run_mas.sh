#!/bin/bash

if [ -f "./.env" ]; then
    export $(grep -v '^#' "./.env" | xargs)
fi

# This folder features DyLAN (Dynamic LLM-Agent Network), brought in vanilla.
# Options:
# --mas_memory:    empty  (vanilla; the other G-Memory baselines are vendored but not wired here)
# --mas_type:      autogen, dylan, macnet   (dispatch is shared; this arm runs dylan)
# --task:          alfworld, fever, pddl, sciworld
#
# Model/backends are resolved by the local proxy (shared/proxy/server.py): the --model string is
# aliased to the proxy's Tinker/Qwen3.6 backend, and every call is logged under DYLAN_TAG.

python3 tasks/run.py \
    --task fever \
    --reasoning io \
    --mas_memory empty \
    --max_trials 15 \
    --mas_type dylan \
    --model Qwen/Qwen2.5-14B-Instruct
