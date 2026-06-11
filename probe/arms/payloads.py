"""Arm-spec parsing and payload loading shared by run_arms and coherence.

Arm names (PROBE_PLAN.md §arms and §in-place-arms):
  alongside the note:  1 (none), 2 (rolled latents), 3 (note-suffix states),
                       4k<k> (selected context states), 5 / 5t (raw text)
  in place of the note: 0 (none — floor), 2i, 3i, 4ik<k>
Bare "4" / "4i" default to k=64.

Payload files under runs/<run>/capture/:
  <ctx>.safetensors           arm2_latents            (run_capture)
  <ctx>_payloads.safetensors  arm3_suffix_states, arm4_selected_states,
                              arm4_positions, arm4_scores (capture_payloads)
"""

import re
from pathlib import Path

import torch
from safetensors.torch import load_file

DEFAULT_K = 64


def parse_arm(arm: str) -> tuple[str, bool, int | None]:
    """'4ik32' → (base '4', inplace True, k 32). k is None except base 4."""
    if arm in ("0", "1", "5", "5t"):
        return arm, arm == "0", None
    if arm in ("2", "3"):
        return arm, False, None
    if arm in ("2i", "3i"):
        return arm[0], True, None
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
    prompt order so the injected sequence preserves A's temporal order."""
    base, _, k = parse_arm(arm)
    if base in ("0", "1", "5", "5t"):
        return None
    if base == "2":
        return load_file(str(capture_dir / f"{context_id}.safetensors"))["arm2_latents"]
    f = capture_dir / f"{context_id}_payloads.safetensors"
    if not f.exists():
        raise FileNotFoundError(
            f"{f} missing — run probe.capture.capture_payloads first")
    t = load_file(str(f))
    if base == "3":
        return t["arm3_suffix_states"]
    states, positions = t["arm4_selected_states"][:k], t["arm4_positions"][:k]
    return states[torch.argsort(positions)]
