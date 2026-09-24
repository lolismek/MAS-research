#!/bin/zsh
# Oracle patching across N (fixed budget N*K=16): Qwen3.5-397B oracle + grounder on Tinker (LIP_ORACLE=tinker; 256K
# context for traces that don't fit 64K), enhanced vs original, M=3, sources = first failed run per task of relay_2x8 /
# relay_4x4 / relay (8x2) / relay_16x1, on the task set TASKS (default the 50-task subset; tasks_injN<n> are nested).
# Traces: lip/traces/injN_<NxK>/. Spend: LIP_EXP_PREFIX=injN_ / LIP_EXP_CAP caps every injN_* and judge/injN_* call
# in-process; per-arm --budget; a tag-scoped watchdog kills only these jobs.
#   EXP_CAP=30 nohup zsh lip/run_inj_sweep.sh &
set -u
cd /Users/alexjerpelea/MAS-memory-research
export LIP_ORACLE=tinker LIP_EXP_PREFIX=injN_ LIP_EXP_CAP=${EXP_CAP:-30} LIP_TINKER_RETRIES=20
TASKS=${TASKS:-lip/data/tasks_injN50.jsonl}
PY=/Users/alexjerpelea/miniforge3/bin/python
L=${LOGDIR:-lip/traces/batch_injN}; mkdir -p $L
stage() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> $L/batch.log }
typeset -A SRC W B
SRC=(2x8 relay_2x8 4x4 relay_4x4 8x2 relay 16x1 relay_16x1)
W=(2x8 3 4x4 3 8x2 4 16x1 4)
B=(2x8 10 4x4 10 8x2 12 16x1 14)      # per-arm backstops; LIP_EXP_CAP is the binding cap
run_all() {   # $1=worker divisor $2=log suffix
  for nk in 2x8 4x4 8x2 16x1; do
    $PY lip/oracle/run_injection.py --all --tasks $TASKS --arm $SRC[$nk] --out injN_$nk --conds enhanced,original --m 3 \
      --workers $(( W[$nk] / $1 > 0 ? W[$nk] / $1 : 1 )) --skip-done --budget $B[$nk] > $L/$nk$2.log 2>&1 &
  done
  wait
}
stage "START exp cap=\$$LIP_EXP_CAP pid=$$"
run_all 1 ""
stage "retry pass 1"; run_all 2 "_retry1"
stage "retry pass 2"; run_all 4 "_retry2"
stage "DONE"
