# Probe report — minimalist latent note-transfer (all arms)

**Date:** 2026-06-11 (arms 1/2/5 morning run; arms 0/2i/3/3i/4k64/4ik64 added same
day) · **Model:** Qwen/Qwen3-8B (bf16, A100 80GB on brev/Hyperstack) ·
**Data:** 38 of 50 synthetic contexts, all arms × 3 paired samples (temp 0.7,
seeds 100–102), identical notes/latents/seeds across the two batches (the new
arms reuse the first run's capture byte-for-byte). Raw outputs in `runs/main/`
(kept locally; `runs/` is gitignored).

## Headline result

| arm | payload tok | verbalized recall | unverbalized recall | Δ verb. vs 1 | Δ unverb. vs 1 |
|---|---|---|---|---|---|
| 0 — no note (floor) | 0 | **0.000** | 0.000 | −0.998 | −0.013 |
| 1 — note only (baseline) | 0 | 0.998 [0.993, 1.000] | 0.013 [0.000, 0.026] | — | — |
| 2 — note + rolled latents | 8 | 0.991 | 0.011 | −0.007 | −0.002 [−0.011, +0.004] |
| 2i — rolled latents **instead of** note | 8 | **0.000** | 0.000 | **−0.998** | −0.013 |
| 3 — note + note-suffix states | 103 | 0.996 | 0.007 | −0.002 | −0.007 [−0.022, +0.009] |
| 3i — note-suffix states **instead of** note | 103 | **0.000** | 0.000 | **−0.998 [−1.000, −0.993]** | −0.013 |
| 4k64 — note + selected context states | 64 | 0.989 | 0.013 | −0.009 | +0.000 [−0.015, +0.018] |
| 4ik64 — selected states **instead of** note | 64 | **0.004** | 0.002 | −0.993 | −0.011 |
| 5 — note + raw context (ceiling) | 4023 | 0.997 | 0.898 [0.860, 0.932] | −0.001 | **+0.885 [+0.836, +0.926]** |

(95% bootstrap CIs over contexts; facts scored by word-boundary string match on
distinctive invented tokens; verbalized/unverbalized split recomputed from each
note at scoring time. Full CIs in `runs/main/analysis/recall.json`.)

## Decision-table outcome: (b), sharpened

**Training-free level-(i) injection carries nothing — not even the note's own
content.** The morning run established 2 ≈ 1 ≪ 5 (info exists and is
recoverable, rolled latents don't deliver it). The new arms close every
remaining loophole:

1. **3i is the pure modality-substitution test and it fails totally.** The
   payload is the *same ~103 tokens B would have read as text*, shipped as
   A's contextualized last-layer states. As text: verbalized recall 0.998.
   As states: **0.000** — not degraded, *zero*, indistinguishable from the
   no-note floor. B confabulates generic domain answers with no trace of the
   note (side-by-side: a note about a dedup-threshold win and a
   `bound_check.py` bottleneck yields answers about ensembles and GBDTs).
2. **It is not a selection problem (arm 4) and not a compression problem
   (arm 3 is 1:1).** Neither a higher-bandwidth payload (103 suffix states)
   nor attention-targeted context states (k=64, SnapKV-style) move
   unverbalized recall alongside the note (Δ −0.007 / +0.000).
3. **It is not the ignored-slots failure mode.** Arm-3 slots draw
   *above-uniform* attention at the max layer (0.18 vs 0.11 uniform; ΔNLL
   +0.017). The model reads the states; it cannot decode language content
   from them at the embedding interface.
4. **The floor is clean and the note is causal.** Arm 0 = exactly 0.000 on
   both splits — facts are not guessable from the scaffold (the matcher's
   invented tokens work), and arm 1 vs arm 0 (+0.998 verbalized) is CORAL's
   "notes carry the knowledge" claim reproduced at 8B scale for free.

Conclusion: at this scale, **last-layer states re-entered at the embedding
floor function as soft prompts with generic gist, not as a language-content
channel**. The remaining training-free option is level (ii) — per-layer
cache-space injection, which preserves A's representations instead of making
B's layer 1 re-process layer-36 states; per-layer suffix states are already
captured (`capture_payloads.py` stores them) so a level-(ii) reader needs no
new capture pass. Otherwise: trained compressor v2 (gist/ICAE-style), win
condition unchanged — close the 0.885 recall gap at ≪4k payload tokens.

## Supporting evidence (gates, all passed)

- **Phase-0:** 10/10 injection unit tests on Qwen3-8B/CUDA (round-trip no-op,
  causality exact — verified fp32 after a bf16 kernel-noise false alarm on
  torch 2.11 — slots attendable, rolling norms, realign matrix, payload
  capture shapes/span/determinism, suffix-injection generation smoke).
- **Capture gate:** notes leave mean 3.64/6 facts unverbalized (lossy as
  intended). Suffix payloads ≈ 100–120 tokens; arm-4 selection confined to
  the transcript span, k_max=128 stored, k subset at use time.
- **Coherence:** arm-3 ΔNLL +0.017 (negligible); all 9 arms produce fluent,
  on-task answers (`runs/main/analysis/side_by_side.md`).
- **Pairing:** new arms reuse the morning run's notes/latents/contexts/seeds
  byte-identically; alongside arms share visible text with arm 1; in-place
  arms share a byte-identical scaffold (verified programmatically). The
  refactored scorer reproduces the morning numbers exactly.

## Caveats

- Single model family/scale (Qwen3-8B writer = reader), single m (8), one k
  (64) actually run — k=32/128 need no recapture if ever wanted.
- Latents/states norm-matched with LatentMAS's realign OFF (their CLI
  default; Qwen3-8B is untied so realign-on is a distinct condition —
  implemented, recipe in `env/GPU_RUN.md`, still unrun). Realign cannot
  rescue the in-place result: it is a linear correction, and the failure is
  total (0.000) with above-uniform attention on the slots.
- String-match scoring is strict; an LLM judge could award partial credit.
  Given zero-vs-0.998 contrasts and confabulated side-by-sides, a judge will
  not change any verdict here.
- Synthetic contexts are templated; external validity beyond the probe is
  explicitly not claimed (plan §risks). A positive arm-5 ceiling licenses
  follow-up mechanisms, not in-loop raw-transcript shipping.

## What this changes for the project

The level-(i) fork is closed with prejudice: rolled summaries (2/2i),
contextualized suffix states (3/3i), and attention-selected context states
(4/4i) all carry ~nothing decodable through the embedding interface, in both
alongside and substitution roles. The project's fork is now binary:
1. **Level (ii) cache-space injection** — the one remaining training-free
   mechanism; per-layer payloads already on disk; ~1 GPU-day to implement
   the reader (K/V projection + RoPE placement + mask surgery); or
2. **Trained compressor v2** — accept training; 0.885 unverbalized headroom
   at 1/40th the tokens is the target the ceiling quantifies.
