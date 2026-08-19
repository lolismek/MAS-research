#!/bin/bash
# One-shot recovery/setup for E2-mini on tigerfish. Everything on /tmp scratch —
# home is over quota. Idempotent: skips finished stages.
# Usage (on tigerfish): bash bootstrap_tigerfish.sh
set -e
S=/tmp/aij2115_scratch
mkdir -p $S/tmp $S/pipcache $S/conda_pkgs $S/envs $S/hf $S/jspace_run/logs
export TMPDIR=$S/tmp PIP_CACHE_DIR=$S/pipcache CONDA_PKGS_DIRS=$S/conda_pkgs HF_HOME=$S/hf
source ~/miniforge3/etc/profile.d/conda.sh

if [ ! -x $S/envs/jspace/bin/python ]; then
    conda create -y -p $S/envs/jspace python=3.12
fi
P=$S/envs/jspace/bin
if ! $P/python -c "import vllm" 2>/dev/null; then
    # CUDA 12.9 driver: cu129 torch + vLLM's own +cu129 wheel (PyPI default is cu130).
    $P/pip install -q --index-url https://download.pytorch.org/whl/cu129 \
        torch==2.13.0 torchvision torchaudio torchcodec
    $P/pip install -q vllm==0.27.1 --no-deps \
        --extra-index-url https://wheels.vllm.ai/0.27.1/cu129
    # vllm deps (resolved against the already-installed cu129 torch), then re-pin
    # the two packages the resolver gets wrong on this driver.
    $P/pip install -q vllm==0.27.1 --extra-index-url https://wheels.vllm.ai/0.27.1/cu129
    $P/pip install -q --force-reinstall --no-deps \
        --index-url https://download.pytorch.org/whl/cu129 torch==2.13.0 torchvision torchaudio torchcodec
    $P/pip install -q openai requests beautifulsoup4 scipy accelerate "numpy<2.4" "cuda-python==12.9.*"
fi
$P/python -c "import torch; assert torch.cuda.is_available(); import vllm; print('stack ok', torch.__version__, vllm.__version__)"

$P/python - <<'EOF'
import os
os.environ.setdefault("HF_HOME", "/tmp/aij2115_scratch/hf")
from huggingface_hub import snapshot_download, hf_hub_download
print(snapshot_download("Qwen/Qwen3.5-4B"))
print(hf_hub_download("neuronpedia/jacobian-lens",
      filename="qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt",
      revision="qwen-n1000"))
print("DOWNLOADS_DONE")
EOF
echo BOOTSTRAP_DONE
