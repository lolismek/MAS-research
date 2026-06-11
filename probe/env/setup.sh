#!/usr/bin/env bash
# Probe environment setup (GPU box or local). Run from the repo root.
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

uv venv .venv --python 3.11
uv pip install --python .venv/bin/python torch transformers safetensors numpy accelerate

.venv/bin/python - <<'EOF'
import torch, transformers
print("torch", torch.__version__, "| cuda:", torch.cuda.is_available(),
      "| transformers", transformers.__version__)
EOF
echo "setup ok — activate with: source .venv/bin/activate"
