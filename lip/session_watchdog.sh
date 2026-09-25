#!/bin/zsh
# Backstop for the per-session cap (the in-process check in harness/llm.py is the primary stop).
# Usage: lip/session_watchdog.sh <session-id> <cap-usd>
# Sums cost_usd of calls.jsonl records tagged session=<id>; at the cap it writes traces/sessions/<id>.STOP (every later
# call of the session raises BudgetExceeded) and kills every process registered in traces/sessions/<id>.pids.
S=$1; CAP=$2
[ -z "$S" -o -z "$CAP" ] && { echo "usage: $0 <session-id> <cap-usd>"; exit 1; }
cd /Users/alexjerpelea/MAS-memory-research
D=lip/traces/sessions; mkdir -p $D
PY=/Users/alexjerpelea/miniforge3/bin/python
while true; do
  SP=$($PY -c "
import json
t=0.0
for l in open('lip/traces/calls.jsonl'):
    if '$S' not in l: continue
    try: r=json.loads(l)
    except Exception: continue
    if r.get('session')=='$S': t+=r.get('cost_usd',0.0) or 0.0
print(round(t,2))")
  echo "$(date '+%H:%M:%S') $SP" > $D/$S.spend
  if [ "$($PY -c "print(int($SP >= $CAP))")" = "1" ]; then
    echo "watchdog: \$$SP >= \$$CAP at $(date)" >> $D/$S.STOP
    [ -f $D/$S.pids ] && for p in $(sort -u $D/$S.pids); do kill $p 2>/dev/null; done
    sleep 5
    [ -f $D/$S.pids ] && for p in $(sort -u $D/$S.pids); do kill -9 $p 2>/dev/null; done
    exit 0
  fi
  [ -f $D/$S.DONE ] && exit 0
  sleep 20
done
