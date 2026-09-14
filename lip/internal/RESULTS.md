# Internal-belief batch — 2026-09-14 (5x3, 140 tasks x 3 arms x 3 runs = 1260 runs, 0 errors, ~$26 Tinker + judge)

| arm | acc (runs) | majority-correct tasks | agent-1 finished |
|---|---|---|---|
| internal_none (belief nowhere) | 0.324 | 40/140 | 61 |
| internal_first (belief in agent 1) | 0.440 | 59/140 | 57 |
| internal_all (belief everywhere) | 0.448 | 64/140 | 81 |

- The belief is worth +12 points when only agent 1 holds it and +12.4 when everyone does: at the aggregate, giving the
  belief to agent 1 alone recovers ~95% of the all-arm gain. The internal-loss gap (all - first) is 0.8 points overall.
- Task-level it is not zero but it is symmetric-ish: 18 tasks all-majority-correct & first-majority-wrong (15 of them
  none-wrong too) vs 13 the other way. Candidates in `traces/batch_internal/analysis.txt` (e.g. frames_093, _680, _230,
  _139, _745, _062).
- Interpretation-lost (failure final == modal none-arm final): first 71/235 failures (30%) vs all 46/232 (20%) as control.
  The excess (~25 runs, ~6% of the arm) is the run-level size of the internal loss.
- Early finishes (allowed in all arms): agent 1 finished 61/57/81 runs; those are 0.56/0.63/0.62 accurate vs 0.28/0.41/0.41
  for handed-off runs. In the first arm 57/420 runs never test propagation. Handed-off runs: none 0.284, first 0.410,
  all 0.407 — the same picture.
- Edge-1 lexical carry (agent-1 handoff mentions the qualifier): first 235/363. But within the first arm the "drops" runs
  are MORE accurate (0.484 vs 0.370): the heuristic misses handoffs that consume the qualifier (state the resolved
  target instead of restating it) — treat carry as a weak proxy; a judge-based check is needed before reporting it.
- Striking pattern in the loss candidates: the qualifier is often IN the handoff (carry=True) yet downstream agents still
  answer the unqualified reading (frames_680 "female" -> Walter Nash 2/3; frames_093 "after 1980" -> 3; frames_117
  "scientific" -> common name). A constraint stated in a handoff is weighted less than the same constraint in the system
  prompt: intent is externalized but not heeded. Worth a judge-based count.
- By type (runs): temporal none .29 / first .40 / all .44; scope .27/.38/.38; entity .50/.67/.53; unit .33/.48/.52.
