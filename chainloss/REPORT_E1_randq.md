# E1-mini: does a hand-off Q&A carry extra signal across the relay edge?

**Question.** At the N=2 handoff, shift A writes its note and is then asked k=3
questions IN THE SAME CONVERSATION IT WORKED IN (so its latent task state can leak
into the answers); the Q&A crosses the edge alongside the note. Does the successor
do better than with the note alone? Two pools:

- `note_randq` — 24 completely off-topic questions (trivia / preferences /
  hypotheticals / explanations; zero task vocabulary). Tests whether latent task
  state leaks through UNRELATED text and whether B can use it.
- `note_epiq` — 12 epistemic probes about the work ("What are you assuming that you
  haven't verified?", "Which part of your note are you least confident about?", ...).
  The on-topic contrast: cheap structured reflection beyond the note.

## Design

- Base mechanics identical to the `note` arm (chainloss relay, FanOutQA first 40
  tasks, N=2, total budget 32000 completion tokens split into two 16k slices,
  gpt-4o -> Qwen/Qwen3.6-35B-A3B via the Tinker proxy, temp 0).
- Question sampling: k=3 per handoff, seeded by sha256(task_id, shift) —
  reproducible (`relay.sample_questions`).
- The Q&A request is appended to shift A's own transcript right after its hand-off
  note (trace-verified: system -> task -> work turns -> HANDOFF_REQUEST -> note ->
  QA_REQUEST -> answers), tool-less.
- Channel: B receives the note (2000-char clip unchanged) in its usual layer, plus
  the Q&A block (questions + answers, clipped at 1500 chars) in its own delimited
  layer framed as "may or may not carry useful signal".
- Q&A tokens are OUTSIDE the relay budget (own ledger: `qa_*` per-shift keys,
  `qa_completion_tokens` in results), so relay work is budget-identical to baseline.
- Baseline cell: `sweeps/full/results.jsonl` note/N=2 (2026-07-30 main run), paired
  per task. Analysis: `metrics/qa_arms_analysis.py e1_qa` (exact two-sided sign
  test + Wilcoxon signed-rank normal approximation on per-task recall deltas).

## Deviations from the E1-mini spec (deliberate, logged)

1. **Budget 32000, not 16000.** The spec said 16k, but the baseline cell was run at
   32k (PLAN.md documents the 16k->32k recalibration). Pairing requires matching.
2. **Q&A allowance 1500 tokens/handoff, not ~600.** At 600 the smoke produced ZERO
   usable Q&A on every handoff: Qwen3.6's think trace alone blows a 600 cap
   (unclosed <think> -> proxy sentinel -> dead marker), and the retry ladder is
   gated once the allowance is spent. 1500 is the smallest round cap at which all
   smoke cells answered (spend 964–1413). Knob: `CHAINLOSS_QA_BUDGET`.

## Confound, documented not fixed (per spec)

Both QA arms spend EXTRA completion tokens (<=1500/handoff, outside the relay
budget) and cross a WIDER channel (note + <=1500 chars of Q&A, ~1.75x baseline
width). Any effect is Q&A-content + width/compute combined; a width-matched control
(note clip 3500) would be the follow-up if either arm had moved (neither did — and
since both moved DOWN despite more width and compute, the confound only strengthens
the null/negative reading).

## Results (40 tasks x N=2 x both arms, $2.99, 0 harness failures)

| arm | n | recall | exact | abstain | no_answer | ctok | qa_ctok | Δrecall (paired) | up/down | sign p | wilcoxon p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| note (baseline) | 40 | 0.550 | 0.300 | 0.000 | 0.050 | 15521 | — | — | — | — | — |
| note_randq | 40 | 0.470 | 0.200 | 0.000 | 0.150 | 17975 | 897 | -0.080 | 3/8 | 0.227 | 0.083 |
| note_epiq | 40 | 0.486 | 0.250 | 0.000 | 0.125 | 16275 | 1482 | -0.064 | 4/11 | 0.118 | 0.182 |

- **Both arms are directionally NEGATIVE, neither significant.** The Q&A side
  channel does not help the successor; if anything it hurts (randq Wilcoxon
  p=0.083, 8 down / 3 up).
- **The drop is a delivery failure, not fact-poor answers** — same signature as the
  main-run N=8 drop: recall|answered is ~flat (0.579 baseline -> 0.553 randq /
  0.556 epiq) while no_answer rises 2/40 -> 6/40 (randq) / 5/40 (epiq). Extra
  inherited layers make more chains burn out uncommitted; mean relay ctok rose
  15.5k -> 18.0k/16.3k despite an identical relay budget.
- **The epiq channel mostly died**: Q&A alive on only 4/40 edges (vs 33/40 randq).
  Epistemic reflection triggers the same <think> spiral as the note wrap-up
  (mean qa_ctok 1482 = the cap, spent on unclosed thinking -> sentinel -> dead
  marker). The epiq cell is therefore effectively a "note + dead-marker layer +
  extra prompt width" control, not a test of epistemic-answer content. A fair
  retest needs a much larger QA allowance (or thinking disabled for the Q&A call).
- Within randq, tasks whose Q&A died did worse than tasks whose Q&A crossed
  (paired Δ -0.200 [n=7] vs -0.055 [n=33]) — but dead Q&A marks spiral-prone
  tasks, so this is correlation, not channel effect.

## Trace-level observations

- **No visible task-state leakage in the off-topic answers.** Scanned all 33 live
  randq Q&A blocks for task entities/vocabulary: zero hits. The answers are fluent,
  generic, fully decoupled from the work context. Example (fanout_003, mid-hunt for
  Taiwanese presidential candidates' birth dates): asked about chairs, ice, and
  superpowers, A answers "Ice floats because water expands and becomes less dense
  when it freezes; ... hydrogen bonds lock into a rigid hexagonal lattice" — not a
  syllable of election state. Whatever latent state exists, it does not surface in
  off-topic text at temp 0, and B gains nothing from it.
- The epiq answers, when they survived, DO carry task-specific epistemic content
  (e.g. fanout_001: "A colleague might confuse the World Car of the Year with ...
  the European Car of the Year"; flags the mm->inch conversion trap) — but they
  survived too rarely (4/40) to move the cell.
- Q&A placement verified in transcripts: the QA request sits immediately after the
  note inside shift 1's full working conversation; shift 2's context is
  system -> task -> handoff_note layer -> handoff_qa layer.

## Verdict

Neither a random-question side channel (latent-state leak) nor epistemic probes
(as implemented) add recoverable signal at the N=2 edge; both arms trend negative
via the familiar burn-out-uncommitted mechanism, despite strictly more channel
width and compute than baseline. E1-mini closes as a null-to-negative result;
epiq's channel death is an infrastructure finding (reflection = spiral) that
must be fixed before epistemic probes can be judged on content.
