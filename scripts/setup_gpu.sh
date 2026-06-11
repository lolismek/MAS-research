#!/usr/bin/env bash
# mini-CORAL GPU box setup (bren). Run from the repo root.
#
#   bash scripts/setup_gpu.sh
#
# Creates a venv, installs deps, pre-downloads Qwen3-8B, runs the model-free
# test suite and the engine smoke. Safety note: agents run arbitrary bash in
# their worktrees --- use an unprivileged user and keep no secrets in the
# environment (the tool layer additionally strips *KEY*/*TOKEN*/*SECRET* vars).
set -euo pipefail

PYTHON=${PYTHON:-python3}
VENV=${VENV:-.venv-minicoral}
MODEL=${MODEL:-Qwen/Qwen3-8B}

echo "== venv =="
$PYTHON -m venv "$VENV"
source "$VENV/bin/activate"
pip install -q --upgrade pip

echo "== dependencies =="
pip install -q pyyaml pytest pytest-asyncio numpy scipy
pip install -q torch transformers accelerate

echo "== model-free test suite =="
python -m pytest tests/ -q

echo "== validate task =="
python -m minicoral validate -c tasks/circle_packing/task.yaml

echo "== pre-download $MODEL =="
python - <<EOF
from huggingface_hub import snapshot_download
snapshot_download("$MODEL")
EOF

echo "== engine smoke (real generation) =="
python scripts/smoke_engine.py --backend hf --model "$MODEL"

echo
echo "Setup complete. Launch the M8 pilot with:"
echo "  python -m minicoral start -c tasks/circle_packing/task.yaml -o configs/gpu-a100.yaml"
