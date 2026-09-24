#!/bin/zsh
# Two-atom internal-belief batch: arms $ARMS (5x3, $RUNS runs, first $LIMIT tasks of tasks_internal_2atom.jsonl) in parallel
# -> two retry passes -> per-atom judge -> summary.
# Budget: LIP_EXP_PREFIX=int2 / LIP_EXP_CAP (default 30) caps EVERYTHING tagged int2* or judge/int2* (task generation,
# smoke, relay, judge, atom judge) in-process before every call; per-arm --budget bounds each arm on its own tags. The
# shared CAP file / lip/watchdog.sh still bound the combined spend of all lip jobs.
#   ARMS="none both1 split13 all" RUNS=2 LIMIT=80 WORKERS=6 BUDGET=4 nohup zsh lip/run_int2_batch.sh &
set -u
cd /Users/alexjerpelea/MAS-memory-research
export LIP_EXP_PREFIX=int2 LIP_EXP_CAP=${LIP_EXP_CAP:-30}
PY=/Users/alexjerpelea/miniforge3/bin/python
ARMS=${ARMS:-"none both1 split13 all"}; WORKERS=${WORKERS:-6}; BUDGET=${BUDGET:-4}; RUNS=${RUNS:-2}; LIMIT=${LIMIT:-0}
L=${LOGDIR:-lip/traces/batch_int2}; mkdir -p $L
T=lip/data/tasks_internal_2atom.jsonl
stage() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> $L/batch.log }
run_arms() {   # $1=workers $2=budget $3=log suffix
  for h in ${=ARMS}; do
    $PY lip/harness/run_task.py --atom-arm $h --tasks $T --n 5 --k 3 --runs $RUNS --all --limit $LIMIT --workers $1 --skip-done --budget $2 > $L/$h$3.log 2>&1 &
  done
  wait
}
stage "START exp cap=\$$LIP_EXP_CAP arms=$ARMS runs=$RUNS limit=$LIMIT workers=$WORKERS budget/arm=\$$BUDGET pid=$$"
run_arms $WORKERS $BUDGET ""
stage "retry pass 1"
run_arms 3 1 "_retry1"
stage "retry pass 2"
run_arms 2 0.5 "_retry2"
if [[ ${SKIP_JUDGE:-0} == 1 ]]; then stage "atom judge SKIPPED (SKIP_JUDGE=1)"; else
  stage "atom judge"
  $PY lip/internal/atom_judge.py --arms $(for h in ${=ARMS}; do echo -n "int2_$h "; done) --workers 12 > $L/atom_judge.log 2>&1
fi
stage "summarize"
$PY lip/internal/summarize_2atom.py > $L/summary.txt 2>&1
cat $L/summary.txt >> $L/batch.log
stage "DONE"
