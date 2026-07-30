# beliefrelay — does belief heterogeneity across relay agents change task accuracy?

**Question.** Inject subjective, task-adjacent "beliefs" into agents' system prompts in
a relay MAS. Does *heterogeneity* of beliefs across agents change end-task accuracy,
versus all agents sharing the same beliefs, versus no beliefs at all?

**MAS.** Homogeneous 3-agent relay (no roles). All agents share one system prompt:
"here is the problem and the previous agent's message; continue/check/improve and pass
on your reasoning." Agent i sees ONLY agent i-1's visible message (the proxy strips
Qwen's `<think>` trace from content, so internal reasoning never crosses the channel).
In the probe arm the belief slot is the only thing that differs between agents.

**Benchmark.** MATH-L5 (134 tasks, HuggingFaceH4/MATH-500 level-5 slice), difficulty-
banded to the model: single-agent pre-screen k=4 at temp 0.7, keep the 0–50%
solve-rate band, take 50 tasks (`pool.json`).

**Beliefs.** Per task, 9 authored opinionated beliefs organized as 3 sets of 3
(`beliefs.json`). Subjective, broadly task-related, never containing the answer or
solution-path quantities (automated numeric-leak check: `harness/check_leakage.py`).
Authored by Claude (the experimenter model), NOT by the subject model.

**Arms** (x 50 tasks x k=2 samples, temp 0.7):
- `probe` — agents 1/2/3 get *different* sets (set 1/2/3 respectively)
- `homo`  — all agents get the *same* set (set index = pool ordinal % 3)
- `none`  — length-matched neutral filler

**Metric.** Accuracy only (validated LaTeX-aware matcher adapted from
camel/harness/scoring.py). Sample-level Wilson CIs + per-task paired deltas.
probe vs homo isolates heterogeneity; homo vs none isolates any-belief-text.

**Infra.** Qwen/Qwen3.6-35B-A3B via the shared Tinker proxy
(multi-benchmark-eval/shared/proxy/server.py, port 8744, `PROXY_DUMP=/dev/null
TINKER_MAX_TOKENS=10000`). Self-metered from calls.jsonl (`harness/spend.py`),
tag prefix `br_`; hard cap $20, runner aborts at $18.

## Run order
```
conda run -n base python beliefrelay/harness/prescreen.py --k 4 --workers 8
conda run -n base python beliefrelay/harness/select_pool.py --n 50
# author beliefs.json (Claude), then:
conda run -n base python beliefrelay/harness/check_leakage.py
conda run -n base python beliefrelay/harness/run_grid.py --arms probe --limit 10   # smoke
conda run -n base python beliefrelay/harness/run_grid.py --arms probe,homo,none --k 2
conda run -n base python beliefrelay/harness/analyze.py
```

Results: `results/prescreen.jsonl`, `results/grid.jsonl` (full transcripts inline),
findings in `REPORT.md`.
