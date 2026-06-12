# Probe report — minimalist latent note-transfer (all arms)

**Date:** 2026-06-11, three batches same day: arms 1/2/5 (morning), arms
0/2i/3/3i/4k64/4ik64 (afternoon), arms 1e/2r/2ir/3kv/3ikv (evening — realign
ablation, level-(ii) KV injection, embedding positive control) · **Model:**
Qwen/Qwen3-8B (bf16, A100 80GB on brev/Hyperstack) · **Data:** 38 of 50
synthetic contexts, all arms × 3 paired samples (temp 0.7, seeds 100–102),
identical notes/contexts/seeds across all batches (later batches reuse the
first run's capture byte-for-byte). Raw outputs in `runs/main/` (kept
locally; `runs/` is gitignored).

## Headline result

| arm | payload tok | verbalized recall | unverbalized recall | Δ verb. vs 1 | Δ unverb. vs 1 |
|---|---|---|---|---|---|
| 0 — no note (floor) | 0 | **0.000** | 0.000 | −0.998 | −0.013 |
| 1 — note only (baseline) | 0 | 0.998 [0.993, 1.000] | 0.013 [0.000, 0.026] | — | — |
| 1e — note **input embeddings** in place of note (control) | 103 | **0.996** [0.987, 1.000] | 0.004 | −0.002 | −0.009 |
| 2 — note + rolled latents | 8 | 0.991 | 0.011 | −0.007 | −0.002 [−0.011, +0.004] |
| 2r — note + rolled latents (**realigned**) | 8 | 0.993 | 0.007 | −0.004 | −0.007 [−0.020, +0.002] |
| 2i — rolled latents instead of note | 8 | **0.000** | 0.000 | −0.998 | −0.013 |
| 2ir — **realigned** rolled latents instead of note | 8 | **0.000** | 0.000 | −0.998 | −0.013 |
| 3 — note + note-suffix states | 103 | 0.996 | 0.007 | −0.002 | −0.007 [−0.022, +0.009] |
| 3i — note-suffix states instead of note (level i) | 103 | **0.000** | 0.000 | **−0.998 [−1.000, −0.993]** | −0.013 |
| 3kv — note + note-suffix **KV cache** (level ii) | 103 | 0.996 | 0.013 | −0.002 | −0.000 [−0.013, +0.008] |
| 3ikv — note-suffix **KV cache** instead of note (level ii) | 103 | **0.928 [0.880, 0.969]** | 0.019 [0.004, 0.039] | **−0.069 [−0.118, −0.029]** | +0.006 [−0.005, +0.022] |
| 4k64 — note + selected context states | 64 | 0.989 | 0.013 | −0.009 | +0.000 [−0.015, +0.018] |
| 4ik64 — selected states instead of note | 64 | 0.004 | 0.002 | −0.993 | −0.011 |
| 5 — note + raw context (ceiling) | 4023 | 0.997 | 0.898 [0.860, 0.932] | −0.001 | **+0.885 [+0.836, +0.926]** |

(95% bootstrap CIs over contexts; facts scored by word-boundary string match on
distinctive invented tokens; verbalized/unverbalized split recomputed from each
note at scoring time. Full CIs in `runs/main/analysis/recall.json`.)

## The finding: the level-(i) failure was the interface, not the information

The same ~103 note tokens, in three transports, in the same scaffold:

| transport | verbalized recall |
|---|---|
| as text (arm 1) | 0.998 |
| as input embeddings (arm 1e, control) | 0.996 |
| as A's last-layer states at the embedding floor (arm 3i, level i) | **0.000** |
| as A's per-layer KV cache rows (arm 3ikv, level ii) | **0.928** |

1. **The harness is sound (arm 1e).** Injecting the note's own
   input-embedding rows through the exact same in-place machinery recovers
   0.996 — the level-(i) zeros are real measurements, not a broken mailbox.
2. **Level (ii) carries language content training-free (arm 3ikv).**
   Reconstructing A's K/V for the note tokens at every layer (from the
   stored per-layer states: input_layernorm → W_k/W_v → per-head k-norm →
   RoPE at B's positions) and splicing them into B's cache delivers 0.928
   vs level (i)'s 0.000 — same information, same positions, different
   injection depth. The remaining −0.069 vs text is mostly exact-token
   loss, not gist loss: misses drop precise values (e.g. a score "0.7576")
   while the surrounding content (file names, mechanisms, next steps)
   survives; the strict matcher gives no partial credit.
3. **Realignment does not rescue the rolled latents (arms 2r/2ir).** The
   LatentMAS ridge-LS matrix is a substantial map on untied Qwen3-8B
   (realigned latents ~orthogonal to the originals, cos ≈ 0.03–0.05), yet:
   alongside Δ unverbalized −0.007 (null, like arm 2's −0.002) and in-place
   exactly 0.000 (like 2i). The arm-2 null now holds under BOTH realign
   settings — the "those vectors are OOD" loophole is closed.
4. **No payload adds information beyond the note (all alongside arms ≈ 1 ≪
   5).** Expected for 3kv (the note's KV contains the note's content and
   nothing more); still true for rolled latents and selected context
   states. The 0.885 unverbalized headroom the ceiling quantifies remains
   unclaimed by every training-free payload tested.

Conclusion: **cache-space injection is a working transport channel for
content the writer has tokenized; embedding-floor injection is not a
channel at all.** Last-layer states re-entered at layer 1 act as
generic-gist soft prompts (the model attends to them above uniform but
cannot decode them); the same content as per-layer K/V is ~fully readable.

## Supporting evidence (gates, all passed)

- **Phase-0: 12/12** on Qwen3-8B/CUDA (and 0.6B). New KV gates: (11)
  rebuilding a span's K/V from its own per-layer hidden states matches a
  plain forward's cache to 2.6e-3 relative (bf16 kernel noise; an absolute
  bound false-alarms at layer 0 where 8B keys reach |K|≈200); (12) greedy
  generation with the span injected in cache space — through the fp16
  storage round-trip — is an EXACT match to plain text generation. This is
  the end-to-end positive control level (i) never had.
- **fp16 payload storage is lossless here:** max |state| over all 38
  contexts' per-layer stacks is ~1.1k, far below fp16 range; all finite.
- **Realign capture:** notes reused byte-identically (`--out-suffix
  _realign`), mean 3.58/6 facts unverbalized; ΔNLL gate for 2r +0.047
  (negligible).
- **Pairing:** all three batches share notes/latents/contexts/seeds;
  alongside arms share visible text with arm 1; in-place arms share a
  byte-identical scaffold. The scorer reproduces earlier batches' numbers
  exactly at every extension.

## Caveats

- Single model family/scale (Qwen3-8B writer = reader), single m (8), one k
  (64) actually run. Writer = reader also means level (ii) here tests
  same-model cache transplant; cross-model would need alignment.
- String-match scoring is strict; 3ikv's 0.928 likely understates content
  transfer (misses are exact-value drops with gist intact). The
  zero-vs-0.998 contrasts are unaffected.
- 3ikv's KV rows are reconstructed from states captured in A's context, so
  they embed A's positional/contextual binding upstream of the slot
  positions; re-RoPE'd at B's positions. The 0.928 says this mismatch is
  mostly tolerable for self-generated suffixes.
- Synthetic contexts are templated; external validity beyond the probe is
  explicitly not claimed (plan §risks).

## What this changes for the project

Level (i) is closed (now with the control that proves the zeros are real),
and the realign ablation is closed. Level (ii) is OPEN and validated as a
transport: the note's KV substitutes for the note at 0.928. What level (ii)
has NOT yet shown is a compression win — the note's KV is the same ~103
rows the text would occupy. The live forks:

1. **Selected-context KV (arm "4kv")** — ship K/V rows of attention-selected
   TRANSCRIPT positions (the arm-4 selection, but injected in cache space
   where arm 4's level-(i) version was null). First arm with a shot at the
   0.885 unverbalized headroom at ≪4k rows; selection already stored
   (k_max=128 positions per context) but per-layer states for selected
   positions need one recapture pass.
2. **Trained compressor v2** — gist/ICAE-style; win condition unchanged
   (close the 0.885 gap at ≪4k payload tokens), now with the alternative of
   emitting CACHE rows instead of embedding rows, which this round showed
   is the decodable interface.
