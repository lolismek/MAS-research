# Fixed-total-budget N sweep (2026-09-23)

Relay of N identical Qwen3.6-35B-A3B agents, K tool calls each, N*K = 16; 155 screened FRAMES tasks x 3 runs per
config (465 runs each, 0 errors after retries). Judge: gpt-oss-120b on Tinker for every point (old relay 8x2 and ceiling
1x16 re-judged). New arms cost $31.65 (relay_2x8 $9.92, relay_4x4 $8.76, relay_16x1 ~$12 incl. judge). Plot: `acc_vs_n.png`.
Raw: `sweep.txt` (`lip/metrics/sweep.py`), `summary.txt` (`lip/metrics/summarize.py`).

| N x K | acc [95% task-bootstrap CI] | vs 1x16 (paired) | pass@3 | handoffs crossed/run | invalid handoff rate |
|---|---|---|---|---|---|
| 1x16 | .667 [.606,.729] | — | .794 | 0 | — |
| 2x8  | .609 [.542,.673] | -.058 [-.103,-.015] | .781 | 0.55 | .059 |
| 4x4  | .589 [.525,.652] | -.077 [-.120,-.032] | .742 | 1.56 | .048 |
| 8x2  | .482 [.417,.553] | -.185 [-.237,-.131] | .652 | 3.25 | .058 |
| 16x1 | .374 [.312,.441] | -.292 [-.351,-.230] | .561 | 4.25 | .119 |

Findings
- Monotone decline with N at fixed total budget; every relay is significantly below the single agent. 2x8 and 4x4 overlap.
- Per-handoff drop rate (gold page seen by agent j, absent from j's handoff) is roughly flat across configs (.37-.43), so
  the run-level loss grows with the number of handoffs: pages lost at some handoff .14 (2x8) / .22 / .28 / .25 (16x1).
- Within a chain, later agents drop more: 8x2 a1 .31 -> a2 .44 -> a3-a7 .45-.51; 16x1 a1 .33 -> a2-a4 ~.47 -> a8-a14 .54-.64.
  Caveat: later agents are reached only on runs nobody finished early (harder runs), so position and difficulty are confounded.

Confounds to report
- Exploration shrinks with K: gold pages opened .21 (1x16) / .19 / .15 / .10 / .02 (16x1); seen (opened or in search
  results) .68 / .68 / .66 / .61 / .51. At 8x2 and 16x1 part of the drop is "never found", not "found then lost".
- 16x1 is degenerate: one call per agent (search OR open), invalid handoffs double (.119), agents often finish early on a guess.
- Early finishes: agent 1 ends 45% of 2x8 runs; handoffs actually crossed per run are far below N-1.
