#!/bin/zsh
# Fixed-total-budget N sweep (N*K = 16): new arms relay_2x8, relay_4x4, relay_16x1 on the 155 screened tasks, 3 runs,
# all three in parallel -> two retry passes -> re-judge the existing relay (8x2) / ceiling (1x16) arms with the current
# judge (gpt-oss-120b) so every point shares one judge -> summary.
# Hard cap: the CAP file (lip/traces/batch/CAP, total logged USD) is checked before every call; lip/watchdog.sh kills
# everything from outside. Per-arm --budget bounds each arm on its own tags.
set -u
cd /Users/alexjerpelea/MAS-memory-research
export LIP_HARD_CAP=${LIP_HARD_CAP:-165}
PY=/Users/alexjerpelea/miniforge3/bin/python
L=${LOGDIR:-lip/traces/batch_sweep}; mkdir -p $L
WORKERS=${WORKERS:-24}; BUDGET=${BUDGET:-16}
stage() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> $L/batch.log }
run_arms() {   # $1=workers $2=budget $3=log suffix
  for nk in 2x8 4x4 16x1; do
    $PY lip/harness/run_task.py --arm relay_$nk --n ${nk%x*} --k ${nk#*x} --runs 3 --all --workers $1 --skip-done --budget $2 > $L/$nk$3.log 2>&1 &
  done
  wait
}
stage "START cap=\$$(cat lip/traces/batch/CAP 2>/dev/null || echo $LIP_HARD_CAP) pid=$$"
stage "re-judge relay + ceiling (background) and arms 2x8 4x4 16x1 ($WORKERS workers each, budget \$$BUDGET per arm)"
$PY lip/internal/rejudge.py --arms relay ceiling --tasks lip/data/tasks_screened.jsonl --workers 8 > $L/rejudge.log 2>&1 &
RJ=$!
run_arms $WORKERS $BUDGET ""
wait $RJ
stage "retry pass 1"
run_arms 8 4 "_retry1"
stage "retry pass 2"
run_arms 4 2 "_retry2"
stage "summarize"
$PY lip/metrics/summarize.py --arms ceiling,relay_2x8,relay_4x4,relay,relay_16x1 > $L/summary.txt 2>&1
cat $L/summary.txt >> $L/batch.log
stage "DONE"
