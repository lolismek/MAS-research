# AutoGen GroupChat

AutoGen **SelectorGroupChat** — a peer round-table (contrast to Magentic-One's star) on
**28 GAIA** tasks. Source: the `magentic-tom` branch, the **most recent, post-stall-fix**
run. Model: `gpt-5.4-mini` via `shared/proxy`. Web access is function tools (no browser).

## Layout

- **`tasks/autogen_gc_tasks.json`** — 28 GAIA tasks (8×L1, 15×L2, 5×L3), partitioned by
  coordination complexity (`web_compute` / `web_only` / `compute_only`). 26 are reused
  from the Magentic GAIA pool (tasks that failed the first time).
- **`harness/`** — the **live system is `split4`** (`scenario_split.py`): 4 agents —
  WebResearcher, Analyst, Critic (review-only), Finalizer (finalize-only). `run_task.py`
  is the runner; `tools.py` = web_search / fetch_url / run_python.
  **`EXPERIMENT_LOG.md` is authoritative** for what's current vs superseded (it wins over
  `README.md` where they disagree). Env: `autogen_gc` (autogen ≥0.6.2).
- **Shared "thinking memory" board** (`--shared-memory`, OFF by default) — an optional
  plug-and-play shared scratchpad layered on `split4` (every participant writes/reads
  free-form in-process notes); see `harness/SHARED_MEMORY.md`. Inspect a board run in
  `judging/viewer_board/` (run `build_board_view.py`, then open `index.html` directly).
- **`traces/split4_openai/`** — the canonical batch: 28 task-UUID dirs (≤5 runs each),
  OpenAI-direct backend (`/o/` route, so reasoning summaries are captured). Committed
  (~9.6 MB). The `split4_openai` namespace is the runner's `<variant>_<backend>` convention.
- **`judging/`** — the **post-stall-fix** evaluation:
  - `analysis_postfix/` — per-trace `verdicts/` (28 JSON) + `inputs_md/` (readable
    transcripts) + the pipeline (`build_inputs.py`, `render_md.py`, `ANALYST_INSTRUCTIONS.md`).
  - `viewer_postfix/` — zero-dependency browser (`index.html` + `traces.json`, committed).
    Open `index.html` directly, or `python -m http.server` in that dir.
  - `FAILURE_ANALYSIS_split4{,_verdicts}.md`, `trace_verdicts_split4.json` — summaries.

> **Note on paths in `EXPERIMENT_LOG.md`:** it is preserved verbatim as the historical
> record, so its commands reference the old `reproduction/…` layout. Here they map to:
> `reproduction/autogen_gc/` → `autogen_gc/harness/`, `reproduction/runs/autogen_gc/` →
> `autogen_gc/traces/`, `analysis_postfix`/`viewer_postfix` → under `autogen_gc/judging/`.

## Re-run (optional)

Traces + analysis are final here. With the proxy up (and `OPENAI_API_KEY` set for `/o/`):

```bash
conda run -n autogen_gc python autogen_gc/harness/run_task.py --all --variant split4 --backend openai --parallel 6
```
