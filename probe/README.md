# Latent note-transfer probe — arms 1, 2, 5

Design + decision table: `../PROBE_PLAN.md` (read it first).
How to run on the GPU box: `env/GPU_RUN.md`. **Do not run models locally.**

| module | what | needs GPU |
|---|---|---|
| `inject/` | level-(i) embedding injection + latent rolling (LatentMAS-adapted, optional `realign=True` for their realignment matrix); `test_inject.py` = Phase-0 gate (8 tests; the original 7 passed on Qwen3-0.6B/8B 2026-06-11, realign test added after) | yes |
| `contexts/` | deterministic synthetic session logs, K=6 planted facts each, self-checking matcher (`make_contexts.py`) | no |
| `capture/` | A-side: CORAL-style reflect note + m=8 rolled latents (arm-2 payload) + verbalized labels | yes |
| `arms/` | B-side runners, arms 1 / 2 / 5 (+5t), paired seeds, identical visible text for 1 vs 2 | yes |
| `analysis/` | `coherence.py` = Phase-2 gates (ΔNLL, slot attention, side-by-side); `score_recall.py` = headline recall table (CPU-only) | coherence only |
| `env/` | `setup.sh`, `run_all.sh`, `GPU_RUN.md` | — |

Arms 3 (note-suffix KV) and 4 (attention-selected context KV) are specified
in the plan but not implemented here, as are the in-place arms 0/2i/3i/4i
(payload *replacing* the note; plan §in-place-arms, added 2026-06-11).
