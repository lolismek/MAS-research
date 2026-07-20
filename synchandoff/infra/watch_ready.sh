#!/bin/bash
rm -f /tmp/aij2115/READY /tmp/aij2115/FAILED
for i in $(seq 1 240); do
  if curl -s -o /dev/null -m 2 http://localhost:8801/v1/models; then echo ok > /tmp/aij2115/READY; exit 0; fi
  if ! pgrep -u aij2115 -f "vllmenv/bin/vllm" >/dev/null; then echo "proc died" > /tmp/aij2115/FAILED; exit 1; fi
  sleep 5
done
echo timeout > /tmp/aij2115/FAILED
