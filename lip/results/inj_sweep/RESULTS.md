# Oracle patching across N (fixed budget N*K = 16), all 155 screened FRAMES tasks

Qwen3.5-397B oracle + grounder (Tinker), Qwen3.6-35B agents, gpt-oss-120b judge, M=3 enhanced vs original.
Run 2026-09-25 under a $100 session budget; stopped by the cap at $99.02 during 4x4.
`python lip/metrics/inj_sweep.py --tasks lip/data/tasks_screened.jsonl --plot lip/results/inj_sweep/loss_vs_n.png`

| N x K | L [95% CI] | paired gain on patched [95% CI] | orig -> enh | patched / eligible |
|---|---|---|---|---|
| 2x8  | +0.030 [+0.010, +0.054] | +0.136 [+0.045, +0.226] | .209 -> .345 | 59 / 75 |
| 4x4  | INCOMPLETE (39 of 80 oracled) | -0.010 [-0.098, +0.078] | .255 -> .235 | 34 / 80 |
| 8x2  | +0.023 [-0.002, +0.048] | +0.070 [+0.008, +0.132] | .221 -> .291 | 86 / 103 |
| 16x1 | +0.009 [-0.012, +0.032] | +0.010 [-0.045, +0.062] | .201 -> .212 | 96 / 120 |
| 8x2, gpt-5.5 oracle (2026-09-14) | +0.031 [+0.007, +0.057] | +0.091 [+0.028, +0.154] | .228 -> .319 | 95 / 103 |

- The earlier flat result on the 50-task subset was the subset: gpt-5.5 was also ~0 there. On all 155 tasks the Qwen
  oracle at 8x2 recovers ~75% of gpt-5.5's L.
- The per-patch gain falls with N (+.136 -> +.070 -> +.010) while w (share of runs failed after a handoff) rises
  (.31 -> .49 -> .59). Fact-bearing addenda help at every N; notes-only addenda hurt at 8x2 and 16x1.
- The 4x4 L is not valid (half the eligible tasks have no oracle output and count as d=0); resume with
  `ARMS=4x4 TASKS=lip/data/tasks_screened.jsonl` (--skip-done) under a new budget.
