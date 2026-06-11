#!/usr/bin/env bash
# Full probe pipeline on the GPU box. Run from the repo root after setup.sh.
#
#   bash probe/env/run_all.sh [MODEL] [RUN_NAME]
#
# MODEL: tiny | dev | full | any HF id   (default: full = Qwen/Qwen3-8B)
# Stages are idempotent: arm outputs are skipped if they already exist, so a
# crashed run can simply be restarted.
set -euo pipefail

MODEL="${1:-full}"
RUN="${2:-main}"
PY=.venv/bin/python

echo "== Phase 0: injection unit tests (gate) =="
$PY -m probe.inject.test_inject --model "$MODEL"

echo "== Phase 1a: synthetic contexts =="
$PY -m probe.contexts.make_contexts --n 50

echo "== Phase 1b: A-side capture (notes + arm-2 latents + labels) =="
$PY -m probe.capture.run_capture --model "$MODEL" --run "$RUN"

echo "== Phase 2: coherence battery on 10 contexts (gate) =="
$PY -m probe.arms.run_arms --model "$MODEL" --run "$RUN" --arms 1,2,5 --samples 1 --limit 10
$PY -m probe.analysis.coherence --model "$MODEL" --run "$RUN" --n 10

echo ""
echo ">>> GATE: inspect runs/$RUN/analysis/coherence.json + side_by_side.md before continuing."
echo ">>> Continue with the full run? [y/N]"
read -r ans
[ "$ans" = "y" ] || exit 0

echo "== Phase 3: full run, 50 contexts x 3 samples =="
$PY -m probe.arms.run_arms --model "$MODEL" --run "$RUN" --arms 1,2,5 --samples 3

echo "== Phase 4: recall scoring =="
$PY -m probe.analysis.score_recall --run "$RUN"

echo "done — see runs/$RUN/analysis/recall_report.md"
