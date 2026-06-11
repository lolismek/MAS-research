# Latent note-transfer probe

Design + decision table: `../PROBE_PLAN.md` (read it first).
How to run on the GPU box: `env/GPU_RUN.md`. **Do not run models locally.**

| module | what | needs GPU |
|---|---|---|
| `inject/` | level-(i) embedding injection, latent rolling (LatentMAS-adapted, optional `realign=True` for their realignment matrix), note-turn payload capture for arms 3/4, level-(ii) cache-space injection (per-layer K/V reconstruction + RoPE at B's positions, arms 3kv/3ikv); `test_inject.py` = Phase-0 gate (12 tests: + KV reconstruction exactness and the KV positive control) | yes |
| `contexts/` | deterministic synthetic session logs, K=6 planted facts each, self-checking matcher (`make_contexts.py`) | no |
| `capture/` | A-side: `run_capture.py` — CORAL-style reflect note + m=8 rolled latents (arm-2 payload; `--realign --out-suffix _realign` for arms 2r/2ir) + verbalized labels; `capture_payloads.py` — arm-3 note-suffix states (per-layer too → 3kv/3ikv) + arm-4 attention-selected context states (eager attention, reuses existing notes) | yes |
| `arms/` | B-side runners, all arms: alongside 1 / 2 / 2r / 3 / 3kv / 4k\<k\> / 5 (+5t), in-place 0 / 1e / 2i / 2ir / 3i / 3ikv / 4ik\<k\>; paired seeds; identical visible text for 1 vs 2, identical scaffold across the in-place family (`payloads.py` = arm parsing + payload loading) | yes |
| `analysis/` | `coherence.py` = Phase-2 gates per payload arm (ΔNLL, slot attention, side-by-side); `score_recall.py` = headline recall table with Δ verb./unverb. vs arm 1 (CPU-only) | coherence only |
| `env/` | `setup.sh`, `run_all.sh`, `GPU_RUN.md` | — |

All arms of the plan (alongside 1/2/3/4/5 and in-place 0/2i/3i/4i) are
implemented and evaluated — full results in `REPORT.md` (2026-06-11, both
batches; all level-(i) payloads null, 3i = 0.000 verbalized). Still open:
the realign-on ablation (recipe in `env/GPU_RUN.md`) and level-(ii)
cache-space injection (unimplemented; the per-layer suffix states it needs
are already stored by `capture_payloads.py`).
