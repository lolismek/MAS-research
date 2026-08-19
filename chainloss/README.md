# chainloss

Does essential information die on MAS channels? A relay (chain) MAS of N shifts
solves FanOutQA under one FIXED total completion-token budget; N ∈ {1,2,4,8} varies
only the number of hand-off crossings. Thesis: accuracy (fact recall) falls with N
in the lossy `note` arm but not in the lossless `transcript` control. Design and
findings: `PLAN.md`.

## Prerequisites

- The shared Tinker proxy running at `PROXY_URL` (default `http://127.0.0.1:8744/v1`)
  from the multi-benchmark-eval worktree (`shared/proxy/server.py`; model alias
  `gpt-4o` → Qwen/Qwen3.6-35B-A3B).
- `chainloss/.env` with `PERPLEXITY_API_KEY=...` (gitignored; copy from the
  multi-benchmark-eval repo root `.env`) — needed by `web_search`.
- conda env `autogen_gc` (openai, requests, bs4).

## Run

```bash
# offline tests (no network)
python chainloss/tests/test_offline.py

# one task, one cell
conda run -n autogen_gc python chainloss/harness/run_task.py \
    --tasks fanoutqa.jsonl --n 8 --arm note fanout_005

# MAIN RUN (the user runs this): first 40 tasks x N{1,2,4,8}, note arm only =
# 160 runs. Expected: ~20-30 min wall at 24 workers, ~$5.
# Parallelism: shifts WITHIN a run are inherently sequential (that's the relay),
# so throughput = concurrent runs; 24 workers is proxy-proven (duet P4 ran 24).
# Resumable: re-running the same --name skips completed (task,n,arm) cells.
conda run -n autogen_gc python chainloss/harness/run_batch.py \
    --tasks fanoutqa.jsonl --limit 40 --ns 1,2,4,8 --arms note --workers 24 --name full

# LATER (attribution): the lossless control, only where the note curve moved —
# e.g. transcript at the N values showing degradation, and/or the back 40 tasks.
# Same --name resumes into the same results file.
conda run -n autogen_gc python chainloss/harness/run_batch.py \
    --tasks fanoutqa.jsonl --limit 40 --ns 4,8 --arms transcript --workers 24 --name full

# mechanism metric (post-hoc, offline): fact survival on the channel
conda run -n autogen_gc python chainloss/metrics/fact_survival.py

# E1-mini (hand-off Q&A arms): note_randq (off-topic questions answered in the
# shift's own work context) and note_epiq (epistemic probes), N=2 only, paired
# against the full-sweep note/n2 cell. Q&A tokens are OUTSIDE the relay budget
# (documented width/compute confound). Results: REPORT_E1_randq.md.
conda run -n autogen_gc python chainloss/harness/run_batch.py \
    --tasks fanoutqa.jsonl --limit 40 --ns 2 --arms note_randq,note_epiq --workers 24 --name e1_qa
conda run -n autogen_gc python chainloss/metrics/qa_arms_analysis.py e1_qa
```

Results: `sweeps/<name>/results.jsonl` + `summary.md` (recall/exact/abstain by
arm x N). Traces: `traces/<arm>/n<N>/<bench>/<id>/run_K/` (result.json,
transcript.json, handoff_notes.txt | work_logs.txt).

## Knobs (env or flags)

- `--budget` / `CHAINLOSS_TOTAL_BUDGET` (default 16000): total completion tokens
  per run, split evenly across shifts.
- `CHAINLOSS_NOTE_MAX_CHARS` (2000): channel width (hard note clip).
- `CHAINLOSS_NOTE_RESERVE` / `CHAINLOSS_COMMIT_RESERVE` (2500/2000): slice tail
  reserved for the wrap-up; auto-scaled to ≤ slice/2.
- `CHAINLOSS_BUDGET_USD` (2.0): per-task USD safety cap (honest UNKNOWN on trip).

## Cost expectations (shakedown-calibrated)

N=1 ≈ $0.006/task median; N=8 note ≈ $0.05–0.08; N=8 transcript ≈ $0.10
(growing inherited-log prompts). Full grid ballpark: $25–45.
