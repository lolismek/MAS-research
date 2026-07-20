#!/bin/bash
# The shared duet/synchandoff proxy, upstream = tigerfish vLLM (not Tinker).
# Same think-strip + tool-call conversion path the whole project calibrated on.
export TINKER_BASE=http://localhost:8801/v1
export TINKER_API_KEY=none
export TINKER_MODEL=Qwen/Qwen3.6-35B-A3B
export TINKER_MAX_TOKENS=28000
export TINKER_ARGS_STYLE=string
export PROXY_PORT=8744
exec /tmp/aij2115/pyenv/bin/python /tmp/aij2115/px/shared/server.py
