"""Arm-spec parsing and payload loading shared by run_arms and coherence.

Arm names (PROBE_PLAN.md §arms and §in-place-arms):
  alongside the note:  1 (none), 2 (rolled latents), 2r (realigned latents),
                       3 (note-suffix states), 3kv (note-suffix KV cache,
                       level ii), 4k<k> (selected context states),
                       5 / 5t (raw text)
  in place of the note: 0 (none — floor), 2i, 2ir, 3i, 3ikv, 4ik<k>,
                       1e (the note's own input embeddings — positive control)
Bare "4" / "4i" default to k=64.

Payload files under runs/<run>/capture/:
  <ctx>.safetensors           arm2_latents            (run_capture)
  <ctx>_realign.safetensors   arm2_latents, realigned (run_capture --realign
                              --out-suffix _realign)  → arms 2r/2ir
  <ctx>_payloads.safetensors  arm3_suffix_states, arm3_suffix_per_layer
                              (→ arms 3kv/3ikv), arm4_selected_states,
                              arm4_positions, arm4_scores (capture_payloads)
Arm 1e needs no file: the runner builds the payload from the note text.
"""

import re
from pathlib import Path

import torch
from safetensors.torch import load_file

DEFAULT_K = 64

_INPLACE_BASES = {"2i": "2", "2ir": "2r", "3i": "3", "3ikv": "3kv", "1e": "1e"}


def parse_arm(arm: str) -> tuple[str, bool, int | None]:
    """'4ik32' → (base '4', inplace True, k 32). k is None except base 4."""
    if arm in ("0", "1", "5", "5t"):
        return arm, arm == "0", None
    if arm in ("2", "2r", "3", "3kv"):
        return arm, False, None
    if arm in _INPLACE_BASES:
        return _INPLACE_BASES[arm], True, None
    m = re.fullmatch(r"4(i?)(?:k(\d+))?", arm)
    if m:
        return "4", bool(m.group(1)), int(m.group(2) or DEFAULT_K)
    raise ValueError(f"unknown arm spec: {arm!r}")


def normalize_arm(arm: str) -> str:
    """Canonical name used in output filenames (bare 4/4i get their k)."""
    base, inplace, k = parse_arm(arm)
    if base == "4":
        return f"4{'i' if inplace else ''}k{k}"
    return arm


def load_payload(capture_dir: Path, context_id: str, arm: str) -> torch.Tensor | None:
    """The vectors to inject for this arm (already norm-matched at capture
    time), or None for the no-payload arms. Arm-4 rows are re-sorted into
    prompt order so the injected sequence preserves A's temporal order.
    For 3kv/3ikv the result is the RAW per-layer state stack [L+1, S, hidden]
    (fp16, not norm-matched) the level-(ii) reader reconstructs K/V from."""
    base, _, k = parse_arm(arm)
    if base in ("0", "1", "5", "5t", "1e"):
        return None  # 1e is built by the runner from the note text
    if base == "2":
        return load_file(str(capture_dir / f"{context_id}.safetensors"))["arm2_latents"]
    if base == "2r":
        f = capture_dir / f"{context_id}_realign.safetensors"
        if not f.exists():
            raise FileNotFoundError(
                f"{f} missing — run probe.capture.run_capture --realign "
                "--notes-from <run> --out-suffix _realign first")
        return load_file(str(f))["arm2_latents"]
    f = capture_dir / f"{context_id}_payloads.safetensors"
    if not f.exists():
        raise FileNotFoundError(
            f"{f} missing — run probe.capture.capture_payloads first")
    t = load_file(str(f))
    if base == "3":
        return t["arm3_suffix_states"]
    if base == "3kv":
        if "arm3_suffix_per_layer" not in t:
            raise KeyError(
                f"{f} has no arm3_suffix_per_layer (captured with "
                "--skip-per-layer?) — recapture without it for the KV arms")
        return t["arm3_suffix_per_layer"]
    states, positions = t["arm4_selected_states"][:k], t["arm4_positions"][:k]
    return states[torch.argsort(positions)]
