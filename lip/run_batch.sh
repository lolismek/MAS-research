#!/bin/zsh
# Full batch: relay (8x2) + ceiling (1x16) in parallel -> retry pass -> summary -> injection (enhanced vs original) -> retry -> summary.
# Hard cap: LIP_HARD_CAP (total logged USD in lip/traces/calls.jsonl) is checked before every API call in every process;
# lip/watchdog.sh additionally kills everything from outside. Errored runs are redone by the retry passes (--skip-done
# skips only error-free runs).
set -u
cd /Users/alexjerpelea/MAS-memory-research
export LIP_HARD_CAP=${LIP_HARD_CAP:-100}
PY=/Users/alexjerpelea/miniforge3/bin/python
L=lip/traces/batch; mkdir -p $L
stage() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> $L/batch.log }
stage "START cap=\$$LIP_HARD_CAP"

stage "relay + ceiling (16 + 16 workers)"
$PY lip/harness/run_task.py --arm relay   --n 8 --k 2  --runs 3 --all --workers 16 --skip-done --budget 60 > $L/relay.log 2>&1 &
R=$!
$PY lip/harness/run_task.py --arm ceiling --n 1 --k 16 --runs 3 --all --workers 16 --skip-done --budget 60 > $L/ceiling.log 2>&1 &
C=$!
wait $R; wait $C
stage "retry pass (errored runs)"
$PY lip/harness/run_task.py --arm relay   --n 8 --k 2  --runs 3 --all --workers 8 --skip-done --budget 20 > $L/relay_retry.log 2>&1 &
R=$!
$PY lip/harness/run_task.py --arm ceiling --n 1 --k 16 --runs 3 --all --workers 8 --skip-done --budget 20 > $L/ceiling_retry.log 2>&1 &
C=$!
wait $R; wait $C
stage "summarize arms"
$PY lip/metrics/summarize.py --arms relay,ceiling > $L/summary_arms.txt 2>&1
cat $L/summary_arms.txt >> $L/batch.log

stage "injection (12 workers)"
$PY lip/oracle/run_injection.py --all --arm relay --out inj --conds enhanced,original --m 3 --workers 12 --skip-done --budget 80 > $L/inj.log 2>&1
stage "injection retry pass"
$PY lip/oracle/run_injection.py --all --arm relay --out inj --conds enhanced,original --m 3 --workers 6 --skip-done --budget 20 > $L/inj_retry.log 2>&1
stage "summarize injection"
$PY lip/metrics/summarize.py --inj --inj-dir inj > $L/summary_inj.txt 2>&1
cat $L/summary_inj.txt >> $L/batch.log
stage "DONE"
