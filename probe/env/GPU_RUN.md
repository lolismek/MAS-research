# Running the probe on the GPU instance (bren)

Everything model-executing runs here; nothing runs on the Mac (it lags it).
One A100/4090-class GPU is enough; Qwen3-8B in bf16 needs ~17GB + activations.

## One-shot

```bash
git clone <repo> && cd MAS-memory-research   # branch open-ended-discovery
bash probe/env/setup.sh
bash probe/env/run_all.sh full main          # full = Qwen/Qwen3-8B
```

`run_all.sh` runs: unit tests → contexts → capture → 10-context coherence
gate (pauses for inspection) → full 50×3 arm run → recall report.
Idempotent: re-running skips finished arm outputs.

## Stage by stage

```bash
.venv/bin/python -m probe.inject.test_inject --model full        # Phase 0 gate: 7/7
.venv/bin/python -m probe.contexts.make_contexts --n 50          # deterministic, self-checks
.venv/bin/python -m probe.capture.run_capture --model full --run main
#   → check capture_summary.json: mean unverbalized should be ~3/6.
#     If ~0, shorten the note instruction (probe/capture/reflect_prompt.py) or raise K.
.venv/bin/python -m probe.arms.run_arms --model full --run main --arms 1,2,5 --samples 1 --limit 10
.venv/bin/python -m probe.analysis.coherence --model full --run main --n 10
#   → GATES: |mean ΔNLL| small (no blow-up), slot attention ≫ 0, side_by_side.md sane.
#     If slot attention ~0: stop, that IS the (negative) finding — see plan §risks.
.venv/bin/python -m probe.arms.run_arms --model full --run main --arms 1,2,5 --samples 3
.venv/bin/python -m probe.analysis.score_recall --run main       # CPU-only, can run anywhere
```

## Knobs

- `--model tiny|dev|full` → Qwen3-0.6B / 4B / 8B (or any HF id). Dev sanity
  pass on the GPU: `bash probe/env/run_all.sh tiny smoke` (~minutes).
- `--arms 1,2,5,5t` — `5t` adds the truncated-raw-text variant
  (`--truncate-tokens`, default 512).
- In-place vs alongside (the design fork) is NOT implemented yet — alongside only.
- `score_recall --llm-judge` — Perplexity judge for facts the string matcher
  misses (needs `PERPLEXITY_API_KEY`; copy `.env` to the box). String match
  is primary; judge verdicts cached in `analysis/judge_cache.json`.

## Outputs

```
runs/<run>/capture/   notes, arm-2 latents (.safetensors), verbalized labels
runs/<run>/arms/      <ctx>_arm<a>_s<s>.json  B continuations
runs/<run>/analysis/  coherence.json, side_by_side.md, recall.json, recall_report.md
```

## Cost estimate

Capture: 50 × (4k-token prefill + ≤320-token gen). Arms: 50 × 3 arms × 3
samples × ≤450-token gen (arm 5 prefills ~2× context). On one A100 with HF
transformers: roughly 3–6 GPU-hours total, in the plan's $5–15 envelope.
Status as of 2026-06-11: Phase-0 unit tests passed 7/7 with Qwen3-0.6B;
capture/arms/coherence code is written but has NOT yet executed end-to-end —
run the `tiny` smoke first and expect possibly a small API fix there.
