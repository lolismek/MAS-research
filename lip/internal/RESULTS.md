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

# Position follow-up — 2026-09-14 (belief skips agent 1; +840 runs, 0 errors, $19 Tinker incl. judge)

User's concern: agent 1 is special (plans the search with the belief; finishes alone in 57/420 first-arm runs). Test: put
the belief in agent 2 only (`second`) vs agents 2-5 (`from_second`), so agent 1 always works on the unqualified question
and hands off an off-track framing that the holder must correct.

**Judge change**: Perplexity quota ran out mid-batch -> judge switched to `openai/gpt-oss-120b` on Tinker (LIP_JUDGE=tinker,
default). All five arms are scored by it; the three earlier arms were re-judged with `lip/internal/rejudge.py`
(911/931 agreement with the gpt-5.4-mini verdicts, 98%; old verdict kept in `score.judge_prev`). Re-judged first-batch
numbers: none .317 / first .440 / all .440 (was .324/.440/.448).

| arm | acc (runs) | majority-correct | finished by agent 1/2 | acc when finished by 1/2 | acc when finished by 3-5 |
|---|---|---|---|---|---|
| none | 0.317 (133/420) | 39/140 | 154 | 0.494 | 0.214 |
| first (agent 1) | 0.440 (185/420) | 59/140 | 183 | 0.617 | 0.304 |
| second (agent 2) | 0.429 (180/420) | 58/140 | 193 | 0.580 | 0.300 |
| from_second (agents 2-5) | 0.445 (187/420) | 65/140 | 173 | 0.561 | 0.364 |
| all | 0.440 (185/420) | 61/140 | 201 | 0.592 | 0.301 |

Paired bootstrap over the 140 tasks (per-task mean accuracy, 5000 resamples):

| comparison | diff | 95% CI |
|---|---|---|
| second - none | +0.112 | [+0.062, +0.162] |
| from_second - second | +0.017 | [-0.033, +0.069] |
| second - first | -0.012 | [-0.055, +0.033] |
| all - from_second | -0.005 | [-0.055, +0.043] |
| all - first | +0.000 | [-0.055, +0.055] |
| all - none | +0.124 | [+0.062, +0.183] |

- Position does not matter: the belief in agent 2 alone is worth +11 points, the same as in agent 1 alone (-1.2 points,
  CI includes zero). Agent 2 overrides agent 1's off-track handoff and the correction survives the remaining relays.
- Mid-chain internal loss is again null: from_second - second = +1.7 points, CI [-3.3, +6.9]. Same size as all - first.
- The only hint of loss is in the runs that reach agents 3-5: from_second 0.364 vs second 0.300 (about 15 runs), i.e.
  when the chain runs long, later holders help a little. Not significant at this n.
- Conclusion strengthened: in a 5-agent relay with K=3, private intent held by ONE agent, wherever it sits, propagates
  about as well as intent held by everyone. The failure mode remains "stated but unheeded", not "never stated".
