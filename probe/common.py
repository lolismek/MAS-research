"""Shared config and helpers for the latent note-transfer probe."""

import json
import os
import random
from pathlib import Path

import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RUNS_DIR = REPO_ROOT / "runs"

# Model tiers. Code is model-agnostic across Qwen3 dense checkpoints
# (same architecture family: QK-norm, GQA, tied/untied embeddings handled by HF).
MODELS = {
    "tiny": "Qwen/Qwen3-0.6B",  # local dev / unit tests (Mac fits this comfortably)
    "dev": "Qwen/Qwen3-4B",     # the plan's dev model (needs ~8GB download)
    "full": "Qwen/Qwen3-8B",    # final numbers on the GPU box
}


def resolve_model(name: str) -> str:
    return MODELS.get(name, name)


def resolve_device(device: str | None = None) -> torch.device:
    if device:
        return torch.device(device)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def resolve_dtype(device: torch.device, dtype: str | None = None) -> torch.dtype:
    if dtype:
        return getattr(torch, dtype)
    # bf16 on CUDA; fp32 elsewhere (MPS bf16 is workable but fp32 keeps the
    # round-trip unit tests tight on small models).
    return torch.bfloat16 if device.type == "cuda" else torch.float32


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def read_json(path: Path | str):
    with open(path) as f:
        return json.load(f)


def write_json(obj, path: Path | str, indent: int = 2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False)


def perplexity_api_key() -> str | None:
    key = os.environ.get("PERPLEXITY_API_KEY")
    if key:
        return key
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("PERPLEXITY_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None
