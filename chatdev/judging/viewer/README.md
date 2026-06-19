# ChatDev trace viewer

Zero-dependency browser for the 15 regenerated ChatDev traces — the analogue of
`autogen_gc/judging/viewer_postfix/`, adapted to ChatDev's phase/role-play structure.

```bash
cd chatdev/judging/viewer
python3 -m http.server 8014      # then open http://localhost:8014/
```

## What it shows

- **Sidebar** — 15 tasks, sorted by relational misalignment (moderate → weak → none),
  with the verdict's one-line summary + outcome. Filter box on top.
- **Transcript tab** — the dialogue grouped by ChatDev phase (`DemandAnalysis →
  LanguageChoose → Coding → CodeReview* → Test* → EnvironmentDoc → Manual`). Each
  message is a bubble colored by role (CEO/CPO/CTO/Programmer/Reviewer/Tester/…). The
  repeated role-context prompt that leads every body is folded behind a "role context"
  disclosure.
- **Code blocks** — collapsed by default (filename + line count + `+adds −dels` badge).
  Click to expand; per-block **full ⇄ diff** toggle. `diff` shows a line diff against the
  **previous version of the same file** earlier in the run — so you can see exactly what
  each `CodeReviewModification` / `TestModification` actually changed.
- **Verdict tab** — the full relational re-judge writeup (`../relational/verdicts/<Task>.md`).
- **Final code tab** — the shipped WareHouse product files.

## Regenerate

`traces.json` is committed. To rebuild it from the raw logs (after re-running traces):

```bash
python3 chatdev/judging/viewer/build_traces.py
```

`build_traces.py` parses each `traces/<Task>/run_N/warehouse/*.log` (splitting on the
`[ts INFO] <Role>: **<header>**` lines), folds role-context, tokenizes bodies into ordered
md/code parts (with best-effort per-block filenames for the diff), and merges in
`result.json`, the WareHouse files, and the relational verdict headline.
