#!/bin/bash
# v2 latent-injection artifact builds: all 30 pilot instances x 8 HF arms,
# split in two halves (half 1 -> server :8802, half 2 -> :8803), A-unsolved
# instances FIRST within each half so driver_latent_waves.sh can start its
# arm waves early. Requires vanilla artifacts (lkv_notekv / lthought_pool)
# — driver_classic.sh builds them first; this script waits.
set -u
cd /tmp/aij2115/synchandoff
export PATH=$HOME/miniforge3/bin:$PATH
PY=/tmp/aij2115/pyenv/bin/python
# session-friendly order: the three traj-session arms first, then the note
# arms, then the thought-session arms (matters when LATENT_MAX_SESSIONS=1)
ARMS=lkv_attn,lkv_last,lkv_rand,lkv_notekv,lthought_soft,lthought_align,lthought_rand,lthought_pool
while true; do
  nvan=$(ls artifacts/*/plain_k12/vanilla.txt 2>/dev/null | wc -l)
  [ "$nvan" -ge 30 ] && break
  sleep 30
done
echo "vanilla present ($nvan) $(date +%H:%M:%S)"
$PY - <<PYEOF
import json
uns = [c["instance_id"] for c in json.load(open("/tmp/aij2115/aunsolved.json"))]
sol = [c["instance_id"] for c in json.load(open("/tmp/aij2115/asolved.json"))]
ordered = uns + sol
h1 = ordered[0::2]
h2 = ordered[1::2]
open("/tmp/aij2115/build_half1.txt", "w").write(",".join(h1))
open("/tmp/aij2115/build_half2.txt", "w").write(",".join(h2))
PYEOF
SYNCHANDOFF_LATENT_BASE=http://localhost:8802 $PY -u build_artifacts.py --k 12 \
  --arms $ARMS --instances "$(cat /tmp/aij2115/build_half1.txt)" \
  > /tmp/aij2115/build_h1.log 2>&1 &
SYNCHANDOFF_LATENT_BASE=http://localhost:8803 $PY -u build_artifacts.py --k 12 \
  --arms $ARMS --instances "$(cat /tmp/aij2115/build_half2.txt)" \
  > /tmp/aij2115/build_h2.log 2>&1 &
wait
echo LATENT_BUILDS_DONE
