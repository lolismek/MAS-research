# Magentic-One

Microsoft's **Magentic-One** (a star topology: an orchestrator that plans + reasons +
self-grades, driving specialist agents incl. a web surfer) on a failure-biased slice of
**GAIA**. Source: the `magentic-tom` branch (the most up-to-date run — a de-Bing'd web
path with a real search-API backend). Model: `gpt-5.4-mini` via `shared/proxy`.

## Layout

- **`tasks/magentic_gaia_tasks.json`** — 15 selected GAIA tasks; **13 executed**
  (8×L1, 4×L2, 1×L3; the 2 attachment tasks excluded). Failure-biased: only 2/13
  succeeded under the original GPT-4o run. The 165-task source pool is in
  `../shared/gaia_pool/`.
- **`harness/`** — `run_task.py` re-executes each task's original MAST `scenario.py`
  verbatim, swapping only the model endpoint. `_debing/` is the WebSurfer monkeypatch
  (intercepts Bing → clean local SERP from a search API), auto-installed via PYTHONPATH
  at subprocess startup. See `harness/README.md` for the env (`magentic_v04`) and the
  full deviation list.
- **`traces/`** — 13 task-UUID dirs, each with `run_N/{console_log.txt, result.json,
  logs/, config.yaml, scenario.py, ...}`. Committed (~63 MB).
- **`judging/`** — `results_13tasks.json` (scored outcomes) + `FAILURE_ANALYSIS.md`
  (headline) + `FAILURE_ANALYSIS_verdicts.md` (per-task). This is **direct trace
  reading** against the MAST taxonomy *and* open-ended — **not** the formal LLM-judge
  pipeline (that one is ChatDev's).

## Re-run (optional)

Magentic's traces + analysis are final here. To re-run you need the external MAST
clone (for each task's original `scenario.py`) — set `MAST_REPO_ROOT`; see
`../shared/mast/README.md`. Then, with the proxy up:

```bash
conda run -n magentic_v04 python magentic_one/harness/run_task.py --all
```
