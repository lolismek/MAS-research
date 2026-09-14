#!/bin/zsh
# Kill every lip API consumer once total logged spend reaches the cap. Independent of the in-process check.
CAP=${1:-100}; [ -f lip/traces/batch/CAP ] && CAP=$(cat lip/traces/batch/CAP)
cd /Users/alexjerpelea/MAS-memory-research
L=lip/traces/batch; mkdir -p $L
while true; do
  S=$(/Users/alexjerpelea/miniforge3/bin/python -c "
import json
t=0.0
for l in open('lip/traces/calls.jsonl'):
    try: t+=json.loads(l).get('cost_usd',0.0)
    except Exception: pass
print(round(t,2))")
  if [ "$(/Users/alexjerpelea/miniforge3/bin/python -c "print(int($S >= $CAP))")" = "1" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WATCHDOG: spend \$$S >= cap \$$CAP -> killing all lip processes" >> $L/batch.log
    pkill -f "lip/harness/run_task.py"; pkill -f "lip/oracle/run_injection.py"; pkill -f "lip/run_batch.sh"; pkill -f "make_tasks.py"
    sleep 5; pkill -9 -f "lip/harness/run_task.py"; pkill -9 -f "lip/oracle/run_injection.py"
    echo "STOPPED $S" > $L/STOP
    exit 0
  fi
  [ -f $L/DONE_MARKER ] && exit 0
  [ -f lip/traces/batch/CAP ] && CAP=$(cat lip/traces/batch/CAP)
  sleep 30
done
