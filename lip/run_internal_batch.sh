#!/bin/zsh
# Internal-belief full batch: arms none/first/all (5x3, 3 runs, 140 tasks) in parallel -> two retry passes -> summary.
# Shares lip/traces/calls.jsonl, the CAP file and lip/watchdog.sh with the external batch: the hard cap is the combined
# spend of both. Per-arm --budget bounds this batch on its own tags. Errored runs are redone by the retry passes.
set -u
cd /Users/alexjerpelea/MAS-memory-research
export LIP_HARD_CAP=${LIP_HARD_CAP:-200}
PY=/Users/alexjerpelea/miniforge3/bin/python
L=lip/traces/batch_internal; mkdir -p $L
T=lip/data/tasks_internal.jsonl
stage() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> $L/batch.log }
run_arms() {   # $1=workers $2=budget $3=log suffix
  for h in none first all; do
    $PY lip/harness/run_task.py --holder $h --tasks $T --n 5 --k 3 --runs 3 --all --workers $1 --skip-done --budget $2 > $L/$h$3.log 2>&1 &
  done
  wait
}
stage "START cap=\$$LIP_HARD_CAP pid=$$"
stage "arms none/first/all (6 workers each)"
run_arms 6 15 ""
stage "retry pass 1"
run_arms 4 5 "_retry1"
stage "retry pass 2"
run_arms 2 3 "_retry2"
stage "summarize"
$PY lip/internal/summarize.py > $L/summary.txt 2>&1
cat $L/summary.txt >> $L/batch.log
stage "DONE"
