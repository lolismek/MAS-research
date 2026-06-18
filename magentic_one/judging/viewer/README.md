# Magentic-One trace viewer

Interactive viewer for the 13 Magentic-One GAIA traces and their failure
verdicts — the Magentic-One counterpart to `autogen_gc/judging/viewer_postfix/`.

It reflects the **broad-lens inter-agent-misalignment re-judging**
(`../relational/`, 2026-06-18): each verdict carries a 4-level misalignment
**strength** (none / weak / moderate / strong) with a plain-language
justification, alongside the unchanged MAST codes. (The strict-lens markdown
still lives in `../FAILURE_ANALYSIS*.md`.)

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
  misalignment-strength badges (none / weak / moderate / strong), plus a filter
  box (id, level, outcome, strength, MAST code, …).
- **Task card + verdict:** the GAIA question, expected vs final answer, the
  highlighted **Where it went wrong** pinpoint, MAST-code chips, the misalignment
  strength, and the per-trace verdict prose (Task / What happened / MAST /
  Inter-agent misalignment / Structural factors / Confidence), parsed from
  `../relational/FAILURE_ANALYSIS_verdicts.md`.
- **Hub-and-spoke transcript:** the ordered console messages. The
  MagenticOneOrchestrator (hub) Task Ledger, routing instructions, and
  finalization are tagged; spokes (WebSurfer / Assistant) are colour-coded. Click
  any message for its full text (WebSurfer page dumps render in monospace).

Note: these console traces have no Selector agent and no private reasoning layer,
and the orchestrator's internal progress-ledger JSON (`is_in_loop` /
`is_request_satisfied`) was not committed — so every verdict is grounded purely
in the public console transcript (cited by line number).

## Rebuild

`traces.json` is generated — regenerate it after editing traces or verdicts:

```bash
python3 build_traces.py
```

It selects the scored run per `../results_13tasks.json` (e.g. `5a0c1adf` →
`run_6`; the others → `run_1`), parses each `console_log.txt` into a timeline,
and merges the task text, results, and the broad-lens verdict prose from
`../relational/FAILURE_ANALYSIS_verdicts.md`.
