# Probe report — minimalist latent note-transfer (arms 1, 2, 5)

**Date:** 2026-06-11 · **Model:** Qwen/Qwen3-8B (bf16, A100 80GB on brev/Hyperstack) ·
**Data:** 38 of 50 synthetic contexts (run stopped early — verdict already outside any
reachable CI movement), 3 arms × 3 paired samples each (temp 0.7, seeds 100–102).
Raw outputs in `runs/main/` (kept locally; `runs/` is gitignored).

## Headline result

| arm | payload tok | verbalized recall | unverbalized recall | Δ unverb. vs arm 1 |
|---|---|---|---|---|
| 1 — note only (baseline) | 0 | 0.998 [0.993, 1.000] | 0.013 [0.000, 0.026] | — |
| 2 — note + m=8 rolled latents | 8 | 0.991 [0.978, 1.000] | 0.011 [0.002, 0.022] | **−0.002 [−0.011, +0.004]** |
| 5 — note + raw context (ceiling) | 4023 | 0.997 [0.991, 1.000] | 0.898 [0.860, 0.932] | **+0.885 [+0.836, +0.926]** |

(95% bootstrap CIs over contexts; facts scored by word-boundary string match on
distinctive invented tokens; verbalized/unverbalized split recomputed from each
note at scoring time.)

## Decision-table outcome: (b)

**The information exists and is recoverable (5 ≫ 1), but training-free
embedding-space injection of rolled latents does not deliver it (2 ≈ 1).**

Per PROBE_PLAN.md §arms, this licenses the v2 direction — a trained compressor
(gist/ICAE-style) — and/or the unimplemented stronger payloads before giving up
on training-free transfer:
- **arm 3 (note-suffix KV)**: A's own states for the note tokens, contextualized
  by the full session — a far higher-bandwidth payload than 8 rolled vectors;
- **level (ii) cache-space injection**: per-layer K/V writing instead of
  last-layer states re-processed from the embedding floor.

## Supporting evidence (Phase-2 gates, all passed)

- **Capture gate:** notes leave a mean **3.64/6 facts unverbalized** — the
  channel is lossy as intended.
- **Coherence:** mean ΔNLL of B's text continuation under the injected prefix
  = **−0.003** — injection does not perturb generation at all.
- **Attention diagnostic:** injected slots receive mean mass ~0.0012 vs ~0.011
  uniform baseline, but **max-layer mass 0.005–0.010 ≈ near-uniform** — the
  slots ARE read by mid/late layers. The failure is therefore *not* the
  "silently ignored slots" mode; the model attends to the latents but cannot
  decode session facts from them. Consistent with the rolled states carrying
  mostly generic continuation direction, not retrievable episodic content.
- **Sanity:** verbalized recall ≈ 1.0 and equal across arms — injection does
  not impair ordinary text reading. Arm-1 unverbalized ≈ 0.013 confirms facts
  are not guessable (the matcher's distinctive invented tokens do their job).
- **Qualitative:** in side-by-side reads (`runs/main/analysis/side_by_side.md`),
  arm 1 and arm 2 confabulate near-identical plausible-but-wrong answers for
  unverbalized facts; arm 5 cites the planted facts with attempt numbers.

## Caveats

- Single model family/scale (Qwen3-8B writer = reader), single m (8), payload
  *alongside* the note only; the in-place/compression fork was not run.
- String-match scoring is strict; an LLM-judge pass could award partial credit
  (e.g. technique named without reason). Given the Δ ≈ 0 with overlapping
  confabulation text, a judge is unlikely to change the arm-2 verdict.
- Synthetic contexts are agent-flavored but templated; external validity
  beyond the probe is explicitly not claimed (see plan §risks).
- A positive arm-5 ceiling licenses follow-up mechanisms; it does NOT say raw
  transcripts are practical in-loop (4k tokens per handoff vs 8).

## What this changes for the project

The cheap hypothesis ("ship A's rolled hidden states next to the note") is
dead at this scale with level-(i) injection. The interesting fork is now:
1. **arm 3 / level (ii)** — test whether *contextualized* states (not rolled
   summaries) cross contexts; still training-free, ~1 GPU-day to add; or
2. **trained compressor v2** — accept training, target the 4k→\<100 token gap
   that arm 5 quantifies (0.885 recall headroom at 1/50th the tokens would be
   the win condition).
