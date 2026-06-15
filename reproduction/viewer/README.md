# split4 trace viewer

A static, zero-dependency browser for the AutoGen **split4** run traces. It renders each
run as the group chat the agents actually saw — one bubble per **published** message —
and lets you drill into the part teammates *couldn't* see:

- **Click a message** → a drawer opens with that turn's **private internal loop** (every
  `web_search` / `fetch_url` / `run_python` call with args + result), the agent's system
  role, and the **published message** highlighted as "the only thing teammates saw." This
  makes the publish-bottleneck gap (where MAST 2.4 distortion lives) visible per turn.
- **Click a 🧭 selector chip** → see the SelectorGroupChat router's **routing context**
  (roles + full conversation-so-far + routing rules) and which member it chose. The
  selector LLM returns only a member name; this shows the input behind that decision.
- The top panel carries the task, expected/final answers, and the two-angle **verdict**
  (task description, how-the-trace-went narrative, MAST codes, genuine-misalignment label,
  critic-gate effect, mechanism, key evidence) from `FAILURE_ANALYSIS_split4.md`.
- Left sidebar lists all 28 traces with outcome / category / misalignment badges; the box
  filters by id, category, or outcome.

## Run it

`traces.json` is a generated artifact (gitignored — it derives from the gitignored
`reproduction/runs/`). Build it, then serve the folder (browsers block `fetch()` from
`file://`, so a plain HTTP server is required):

```bash
python3 reproduction/viewer/build_traces.py          # writes traces.json
cd reproduction/viewer && python3 -m http.server 8011 # then open http://localhost:8011/
```

## Files
| path | role |
|---|---|
| `build_traces.py` | reconstructs each run's timeline (selector calls + per-turn private loops + published messages) from `runs/.../wire_log.jsonl` + `result.json`, joins the split4 verdicts, writes `traces.json` |
| `index.html` | the viewer (vanilla HTML/CSS/JS, no build step) |
| `traces.json` | generated; not committed |

The reconstruction is keyed off the proxy `wire_log.jsonl` (per-trace slice of
`raw_calls.jsonl`): selector calls are the single-message rows containing the selector
prompt; an agent turn is the run of rows between two selectors, and that run's last row
holds the full accumulated private context + the published `reply`.
