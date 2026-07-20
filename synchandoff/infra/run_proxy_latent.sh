#!/bin/bash
# SECOND proxy instance (piranha) for LATENT-arm B episodes: identical
# proxy_server.py (think-strip + XML tool-call parsing), but upstream is the
# latent server on tigerfish via the :8802 ssh tunnel instead of vLLM :8801.
# Latent phase-2 shards point SYNCHANDOFF_LLM_BASE at http://localhost:8745/m/v1.
#
# Tunnel (start once on piranha, same pattern as the :8801 one):
#   ssh -f -N -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes \
#       -i /tmp/aij2115/tunnel_key -L 8802:localhost:8802 \
#       aij2115@tigerfish.cs.columbia.edu
export TINKER_BASE=http://localhost:8802/v1
export TINKER_API_KEY=none
export TINKER_MODEL=latent-qwen
export TINKER_MAX_TOKENS=8000
export TINKER_ARGS_STYLE=string
export PROXY_PORT=8745
export PROXY_UPSTREAM_TIMEOUT=3600
export PROXY_DUMP=/tmp/aij2115/px/latent/raw_calls_latent.jsonl
# NB: /tmp/aij2115/px/latent/server.py is the REPO's infra/proxy_server.py
# (has the PROXY_UPSTREAM_TIMEOUT knob); the live :8744 text proxy at
# px/shared/server.py is untouched.
exec /tmp/aij2115/pyenv/bin/python /tmp/aij2115/px/latent/server.py
