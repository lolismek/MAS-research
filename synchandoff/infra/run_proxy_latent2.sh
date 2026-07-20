#!/bin/bash
# Second latent proxy (piranha :8746) -> tunnel :8803 -> latent server
# instance 2 on tigerfish GPU 0 (free since ~11:00 2026-07-20; if a
# non-aij2115 job reappears on GPU 0, stop instance 2 and fall back to one).
# Tunnel: ssh -i /tmp/aij2115/tunnel_key -o BatchMode=yes \
#   -o StrictHostKeyChecking=accept-new -o ExitOnForwardFailure=yes -N -f \
#   -L 8803:localhost:8803 aij2115@tigerfish.cs.columbia.edu
export TINKER_BASE=http://localhost:8803/v1
export TINKER_API_KEY=none
export TINKER_MODEL=latent-qwen
export TINKER_MAX_TOKENS=8000
export TINKER_ARGS_STYLE=string
export PROXY_PORT=8746
export PROXY_UPSTREAM_TIMEOUT=3600
export PROXY_DUMP=/tmp/aij2115/px/latent/raw_calls_latent2.jsonl
exec /tmp/aij2115/pyenv/bin/python /tmp/aij2115/px/latent/server.py
