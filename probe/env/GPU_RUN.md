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
.venv/bin/python -m probe.inject.test_inject --model full        # Phase 0 gate: 8/8
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

## New arms 0 / 2i / 3 / 3i / 4k\<k\> / 4ik\<k\> (extend the main run)

These reuse the main run's notes, latents, contexts, and seeds, so the new
outputs land in `runs/main/` and pair with the existing arms 1/2/5. Upload
the main run from the Mac first:

```bash
rsync -av runs/main/ <box>:~/MAS-memory-research/runs/main/
```

Then on the box:

```bash
.venv/bin/python -m probe.inject.test_inject --model full            # now 10/10
.venv/bin/python -m probe.capture.capture_payloads --model full --run main --limit 38
#   → arm-3/4 payloads (note-suffix + attention-selected states), eager attention,
#     idempotent. ~45MB/ctx with per-layer states (--skip-per-layer to halve).
.venv/bin/python -m probe.arms.run_arms --model full --run main \
    --arms 0,2i,3,3i,4k64,4ik64 --samples 1 --limit 2                # smoke, eyeball
.venv/bin/python -m probe.analysis.coherence --model full --run main --arm 3 --n 10
#   → ΔNLL gate vs arm 1 (identical text); --arm 3i gates vs the arm-0 scaffold
#     (needs arm-0 s0 outputs first).
.venv/bin/python -m probe.arms.run_arms --model full --run main \
    --arms 0,2i,3,3i,4k64,4ik64 --samples 3 --limit 38               # full eval
.venv/bin/python -m probe.analysis.score_recall --run main           # one paired table
```

`--limit 38` matches the main run's early stop. k is subset at use time from
the stored k_max=128, so 4k32/4k128 need no recapture. In-place arms read
their verdict off the VERBALIZED column (plan §in-place-arms).

## Round 3: realign (2r/2ir), level-(ii) KV (3kv/3ikv), embedding control (1e)

These also extend `runs/main` (one paired table at the end). The realigned
latents are recaptured with `--out-suffix _realign` so they land NEXT TO the
originals instead of clobbering them; notes are reused byte-for-byte. The KV
arms reconstruct A's cache rows from the per-layer suffix states
`capture_payloads` already stored — no new capture pass. Arm 1e needs no
capture at all (the runner embeds the note text itself).

```bash
.venv/bin/python -m probe.inject.test_inject --model full            # now 12/12
#   → tests 11/12 are the KV gates: reconstruction exactness + positive
#     control (greedy KV-injected == greedy text). Do NOT run the KV arms
#     if either fails.
.venv/bin/python -m probe.capture.run_capture --model full --run main \
    --realign --notes-from main --out-suffix _realign --limit 38
.venv/bin/python -m probe.arms.run_arms --model full --run main \
    --arms 1e,2r,2ir,3kv,3ikv --samples 1 --limit 2                  # smoke, eyeball
.venv/bin/python -m probe.analysis.coherence --model full --run main --arm 2r --n 10
#   → ΔNLL + slot-attention gates for the realigned latents (embeds-space
#     arms only; 3kv/1e are gated by tests 11/12 and by being controls)
.venv/bin/python -m probe.arms.run_arms --model full --run main \
    --arms 1e,2r,2ir,3kv,3ikv --samples 3 --limit 38                 # full eval
.venv/bin/python -m probe.analysis.score_recall --run main           # one paired table
```

Reading the new rows: 1e ≈ arm 1 validates the level-(i) in-place harness
(if it is ≈ 0 instead, every level-(i) zero is suspect). 2r/2ir test whether
the OOD-correction matrix changes the arm-2/2i nulls. 3ikv is the level-(ii)
substitution test — the note's own KV instead of its text.

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
