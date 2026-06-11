#!/usr/bin/env bash
# Probe environment setup (GPU box or local). Run from the repo root.
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

uv venv .venv --python 3.11
uv pip install --python .venv/bin/python torch transformers safetensors numpy accelerate

# Default torch wheels may target a newer CUDA than the box's driver
# (Hyperstack A100s ship driver CUDA 12.8; default wheel was cu130).
if command -v nvidia-smi >/dev/null 2>&1; then
    if ! .venv/bin/python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
        echo "torch wheel doesn't match driver — reinstalling cu128 build"
        uv pip install --python .venv/bin/python --reinstall torch \
            --index-url https://download.pytorch.org/whl/cu128
    fi
fi

.venv/bin/python - <<'EOF'
import torch, transformers
print("torch", torch.__version__, "| cuda:", torch.cuda.is_available(),
      "| transformers", transformers.__version__)
EOF
echo "setup ok — activate with: source .venv/bin/activate"
