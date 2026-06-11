# Latent note-transfer probe — arms 1, 2, 5

Design + decision table: `../PROBE_PLAN.md` (read it first).
How to run on the GPU box: `env/GPU_RUN.md`. **Do not run models locally.**

| module | what | needs GPU |
|---|---|---|
| `inject/` | level-(i) embedding injection + latent rolling (LatentMAS-adapted); `test_inject.py` = Phase-0 gate, 7/7 passed on Qwen3-0.6B 2026-06-11 | yes |
| `contexts/` | deterministic synthetic session logs, K=6 planted facts each, self-checking matcher (`make_contexts.py`) | no |
| `capture/` | A-side: CORAL-style reflect note + m=8 rolled latents (arm-2 payload) + verbalized labels | yes |
| `arms/` | B-side runners, arms 1 / 2 / 5 (+5t), paired seeds, identical visible text for 1 vs 2 | yes |
| `analysis/` | `coherence.py` = Phase-2 gates (ΔNLL, slot attention, side-by-side); `score_recall.py` = headline recall table (CPU-only) | coherence only |
| `env/` | `setup.sh`, `run_all.sh`, `GPU_RUN.md` | — |

Arms 3 (note-suffix KV) and 4 (attention-selected context KV) are specified
in the plan but not implemented here; the `in-place` payload variant (vs
`alongside`) is also not implemented.
