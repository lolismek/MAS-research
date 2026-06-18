# Magentic-One trace viewer

Interactive viewer for the 13 Magentic-One GAIA traces and their failure
verdicts — the Magentic-One counterpart to `autogen_gc/judging/viewer_postfix/`.

## Run

```bash
cd magentic_one/judging/viewer
python3 -m http.server 8014
# open http://localhost:8014/
```

(Browsers block `fetch()` over `file://`, so it must be served over HTTP. GitHub
won't render it live — clone and serve locally.)

## What it shows

- **Sidebar:** all 13 traces with outcome / level / `~correct` (substantive) /
  misalignment badges, plus a filter box (id, level, outcome, MAST code, …).
- **Task card + verdict:** the GAIA question, expected vs final answer, primary
  cause, MAST-code chips, and the per-trace verdict prose (Task / What happened /
  misalignment / structural factors), parsed from `FAILURE_ANALYSIS_verdicts.md`.
- **Hub-and-spoke transcript:** the ordered console messages. The
  MagenticOneOrchestrator (hub) Task Ledger, routing instructions, and
  finalization are tagged; spokes (WebSurfer / Assistant) are colour-coded. Click
  any message for its full text (WebSurfer page dumps render in monospace).

Note: these console traces have no Selector agent and no private reasoning layer,
so the orchestrator's internal progress-ledger JSON (the `is_in_loop` /
`is_request_satisfied` flags the verdicts cite) is not part of the transcript.

## Rebuild

`traces.json` is generated — regenerate it after editing traces or verdicts:

```bash
python3 build_traces.py
```

It selects the scored run per `../results_13tasks.json` (e.g. `5a0c1adf` →
`run_6`; the others → `run_1`), parses each `console_log.txt` into a timeline,
and merges the task text, results, and verdict prose.
