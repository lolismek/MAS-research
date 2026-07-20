#!/bin/bash
# G1 smoke on the GPU stack: proxy up -> 1 chat call -> 1-instance k=3 agent run.
set -e
export PATH=$HOME/miniforge3/bin:$PATH
export UDOCKER_DIR=/tmp/aij2115/udocker SYNCHANDOFF_ENV=udocker
export SYNCHANDOFF_LLM_BASE=http://localhost:8744/m/v1
export SYNCHANDOFF_LLM_LOG=/tmp/aij2115/synchandoff/llm_calls_gpu.jsonl
if ! curl -s -o /dev/null -m 2 http://localhost:8744/docs; then
  setsid nohup /tmp/aij2115/run_proxy.sh > /tmp/aij2115/proxy.log 2>&1 < /dev/null &
  for i in $(seq 1 20); do curl -s -o /dev/null -m 2 http://localhost:8744/docs && break; sleep 2; done
fi
echo "=== direct chat through proxy ==="
curl -s -m 120 http://localhost:8744/m/v1/chat/completions -H "Content-Type: application/json" \
  -d "{\"model\":\"gpt-4o\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: PROXY_CHAIN_OK\"}],\"max_tokens\":2000}" | head -c 400
echo
echo "=== agent smoke (flask, k=3) ==="
cd /tmp/aij2115/synchandoff
/tmp/aij2115/pyenv/bin/python -u phase1_runner.py --candidates /tmp/aij2115/flask_only.json --k 3 2>&1 | tail -3
