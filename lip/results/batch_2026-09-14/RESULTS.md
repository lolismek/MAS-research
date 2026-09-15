# Big batch 2026-09-14 (commit f3d73e78 / 11746da2)

155 screened FRAMES tasks, offline pinned corpus, relay model Qwen3.6-35B-A3B (Tinker), oracle gpt-5.5, grounder/judge gpt-5.4-mini.

## Arms (3 runs per task)
| arm | acc | task-majority | any-of-3 | gold opened | gold seen | seen-then-absent-from-handoff | cost |
|---|---|---|---|---|---|---|---|
| relay N=8 K=2 | 0.484 | 0.465 | 0.658 | 0.10 | 0.61 | 0.28 | $9.93 |
| ceiling N=1 K=16 | 0.673 | 0.697 | 0.800 | 0.21 | 0.68 | — | $12.98 |

Failed relay runs: 240; 53 of them had every gold page seen by some agent. Invalid handoffs 88/~3700.

## Injection (first failed relay run per task; oracle picks ONE edge; suffix resampled M=3 per condition)
102 tasks with a failed run -> 95 injected (1 declined, 6 unusable oracle output).

| condition | runs | success | tasks-any |
|---|---|---|---|
| original | 285 | 0.228 | 0.379 |
| enhanced | 285 | 0.319 | 0.453 |

Paired enhanced - original: **+0.091, 95% bootstrap CI [+0.028, +0.151], n=95**. Wins 24 / losses 11 / ties 60.
Ceiling on the same 95 tasks: 0.530.

Slices (paired diff):
- source run mechanically lost a seen gold page before the edge: n=64, **+0.120** [+0.047, +0.193]; no mechanical loss: n=31, +0.032 [-0.075, +0.140]
- addendum kept >=1 fact sentence: n=66, +0.116 [+0.035, +0.202]; notes only: n=29, +0.034 [-0.023, +0.103]
- by edge i: 2: -0.02 (19), 3: +0.11 (22), 4: +0.04 (15), 5: +0.13 (10), 6: +0.09 (11), 7: +0.22 (9), 8: +0.19 (9)

Grounding kept 342/422 sentences (facts 147/176, notes 195/246).

Caveats: original succeeds 23% from the same "failed" prefix (resampling variance); receivers sometimes ignore a note that states the gold value (frames_090); the mechanical found-but-lost flag counts title omissions that may be carried in other words.
Spend: arms $22.9, injection ~$50; total log $96 incl. the parallel internal-belief batch (~$16).
