# DyLAN-MATH: inter-agent misalignment case studies

15 traces (MATH-500 level 5, 12 baseline failures + 3 controls), gpt-5.4-mini
agents, judged 2026-06-11 by the gpt-5.5 two-stage judge. Raw material:

- per-trace judge verdicts: `judged/new/dylan-math/*.json` (stage-A close
  reading + stage-B MAST labels, every flag with a verbatim quote)
- mechanical trajectories: `../dylan/trajectory_analysis.json`
  (regenerate with `../dylan/analyze_trajectories.py`)
- full transcripts: `../runs/dylan-math/<id>/run_*/transcript.txt`
  (local disk only, gitignored)
- aggregate tables: `../report/gen_modes.tex`, `gen_outcomes.tex`

## Fingerprint (n=15)

| mode | DyLAN-MATH | ChatDev | Magentic | reading |
|------|-----------|---------|----------|---------|
| 2.4 Information Withholding | **2** | 15 | 4 | broadcast debate shares everything; the 2 hits are parser-induced loss (below) |
| 2.5 Ignored Other Agent's Input | **4** | 15 | 13 | rare, and 3/4 co-occur with the parser collision |
| 2.6 Action-Reasoning Mismatch | 11 | 12 | 13 | wrong derivations behind right-looking steps — capability-style |
| 3.2 Incorrect Verification | 8 | 13 | 13 | peer scoring endorses wrong solutions |
| 3.3 No/Incomplete Verification | 7 | 13 | 13 | |

DyLAN's category-2 profile is the inverse of ChatDev's: a fully-connected
debate topology has no private state to withhold and every reply is in every
prompt. The cat-2 failures that DO occur are almost all one structural
mechanism — the **answer/score extraction collision**: from round 2 the
framework prompt demands an updated answer AND boxed `[[1,5,2,...]]` peer
scores in the same reply, while `ans_parser` records the LAST `\boxed{}`
expression. An agent that boxes its scores after its answer gets the score
matrix recorded as its "answer", and consensus / final selection then operate
on garbage. Layer-1 cross-check: every judge 2.4/2.5 hit lands on a trace
where `trajectory_analysis.json` shows `parser_masked` events or a
ranker-deactivated-correct agent — the two layers agree case-by-case.

Corrected outcomes: 10/15 semantically correct (8/15 by raw `is_equiv` + 2
grading artifacts, see end). Of the 5 real failures: 3 structural losses
(cases 1–3 below), 2 capability (geometry_880, precalculus_768 — no agent
ever had the right answer).

## Case 1 — counting_and_probability_525: unanimous-correct team outputs a score matrix

The flagship structural loss. Round 1: 4/7 agents correctly get 144 (gap
method). Round 2: **all 7 agents converge on 144** — the debate worked
perfectly as a reasoning process. But several agents boxed their peer scores
after their answer, so the framework recorded e.g. `[[2,5,5,5,5,1,2]]`
instead of 144; consensus over recorded answers never fires, the ranker keeps
two round-2 replies, and the run ends with
`System final answer: [[5,5,5,5,5,5,5]]` vs expected 144.

- Judge 2.4: "the correct answer appeared in the agent reply but did not
  reach the framework's recorded answer state" — information produced but
  lost at the channel boundary.
- Judge 2.5 (independent of the parser bug): Agent 2 scored Agent 4's
  correct gap-method solution as if it had made a different error — peer
  scores inconsistent with the replies being scored.
- Layer 1: `per_round correct/active` = 4/7 → **7/7** → 2/2;
  `parser_masked` events for AlgebraExpert (r2) and
  CountingProbabilitySpecialist (r3); 5 correct agents deactivated by the
  ranker before round 3.

This was also the judge-validation trace: the judge reconstructed the
mechanism unaided from the transcript preamble + per-reply
`[framework-recorded answer: ...]` annotations.

## Case 2 — intermediate_algebra_1197: correct answer derived twice, returned `[[2,4,1,2,1,2,1]]`

Hard polynomial problem (expected 3/56). Round 1: 0/7 correct. Round 2:
AlgebraExpert and GeometryWizard both derive 3/56 — genuine correction
through debate. But AlgebraExpert boxes its score list after `\boxed{3/56}`,
so the framework records `[[2,1,1,1,2,1,1]]`; GeometryWizard (whose recorded
answer WAS 3/56) is then **deactivated by the listwise ranker** before round
3 (judge 2.5: "the ranker did not use that contribution in the final
round"). Final answer: AlgebraExpert's round-3 score matrix.

- Layer 1: corrections=2 (round 1→2), `deactivated_correct`=GeometryWizard,
  `parser_masked` for AlgebraExpert in rounds 2 AND 3.
- Double structural failure: the parser collision corrupts one correct
  agent's channel, the ranker discards the other correct agent.

## Case 3 — prealgebra_1646: correct minority answer dismissed, then conformity flip

Angle-trisection geometry (expected 80). Round 1: only NumberTheoryScholar
gets 80; the majority sits on 130/50/110. AlgebraExpert's round-2 reply
explicitly scores it down: "Agent 5: misread the diagram, incorrect → 1".
NumberTheoryScholar then **abandons its own correct answer and flips to the
majority's 130** — the only conformity flip in the whole MATH batch
(`conformity_flips`: dropped "80" → "130"). The two ranker-surviving agents
both finish on 130, and the parser collision converts the final reply into
`[[4,4,1,4,4,3,4]]` anyway.

- Judge 2.5: "the correct Round 1 answer was received in the shared context
  but was dismissed and then abandoned."
- This is the classic social-pressure failure MAST's 2.5 describes, and the
  one case where it caused the loss independent of the parser bug (the
  surviving answers were wrong regardless).

## Case 4 — intermediate_algebra_1388: consensus reached, equivalence machinery fails

Round 1, 5 of 6 activated agents box the correct set `-2,1`; the run
early-stops on consensus. Marked wrong only because gold orders the set
`1,-2` and `is_equiv` compares strings — a **grading artifact, not a run
failure** (the baseline screen failed on the identical artifact, so it's
also not a real baseline failure). Judge flagged 2.5 against the framework
(consensus received but the stop/recording behavior didn't honor it cleanly)
and caught the false `is_equiv` verdict in stage A. Same class as
algebra_2626 (`\$32,\!348` vs `32348`). Both excluded from the corrected
10/15 outcome count.

## What the non-cat-2 failures look like

- **geometry_880 / precalculus_768** (capability): no agent ever produced
  the expected answer (`ever_correct=false` for 880's target; 768 converged
  on right roots but mangled final formatting). Debate amplified a shared
  wrong assumption (880: ambiguous wall dimensions) — judge labels 2.6 +
  3.2/3.3, no 2.4/2.5.
- The 10 correct runs still carry near-universal 1.3/1.5 (framework prints
  empty post-consensus rounds; redundant calls after early-stop conditions
  met) and frequent 2.6 in individual wrong derivations that the consensus
  machinery correctly outvoted.

## Takeaway for the structural-vs-capability thesis

Same model, same judge, third architecture, third fingerprint: ChatDev
(pipeline + shared store) → 2.4-dominant; Magentic (star) → 2.5-dominant;
DyLAN (broadcast debate) → cat-2 nearly absent, verification-dominated.
Where DyLAN does lose information it is not agents withholding it — it is
the framework's own answer-extraction channel and ranker discarding answers
that are sitting in plain sight in the transcript. Inter-agent misalignment
tracks the information topology, not the model.
