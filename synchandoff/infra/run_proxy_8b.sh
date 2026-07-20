#!/bin/bash
# v2 text proxy (piranha): upstream = tigerfish vLLM Qwen3-8B via the :8804
# ssh tunnel. Same proxy_server.py (think-strip harmless under no-think, XML
# tool-call conversion, TINKER_ARGS_STYLE=string for vLLM's spec-compliant
# string arguments). During 35B decommission smoke this runs on :8747; after
# decommission it is relaunched on :8744 so every wave script works unchanged.
# Tunnel (once, on piranha):
#   ssh -i /tmp/aij2115/tunnel_key -o BatchMode=yes \
#     -o StrictHostKeyChecking=accept-new -o ExitOnForwardFailure=yes -N -f \
#     -L 8804:localhost:8804 aij2115@tigerfish.cs.columbia.edu
export TINKER_BASE=http://localhost:8804/v1
export TINKER_API_KEY=none
export TINKER_MODEL=${SYNCHANDOFF_MODEL:-Qwen/Qwen3-8B}
# thinking-ON regime with the YaRN 65536 window: think traces need output
# budget (v1 used 28000 at 65536; 8000 fits 34k prompts w/ big margin)
export TINKER_MAX_TOKENS=${SYNCHANDOFF_MAXTOK:-8000}
export TINKER_ARGS_STYLE=string
export PROXY_PORT=${PROXY8B_PORT:-8744}
exec /tmp/aij2115/pyenv/bin/python /tmp/aij2115/px/shared8b/server.py
