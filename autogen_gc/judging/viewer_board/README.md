# Shared-memory board viewer

Zero-dependency browser viewer for `--shared-memory` board runs. Same shape as the
`viewer_postfix` viewer: the main panel is the **group chat** (published messages);
**click a message** to open its private trace in a drawer, **click a Selector chip**
for routing. Per message, the drawer shows:

- the **scratchpad the agent read** at turn start (the injected board block);
- the **private ReAct loop** — each round's reasoning summary (💭) + tool calls;
  `add_note` / `revise_note` calls are flagged as **board write**;
- the one message it **published** to the group.

Selector chips show the choice, the routing note it wrote to the board, its reasoning
summary, and the full routing prompt (with the board spliced into `{board}`).

## Use

```bash
python build_board_view.py     # regenerates data.js from autogen_gc/traces/split4_board*/
open index.html                # opens straight from disk — data is embedded in data.js
```

`build_board_view.py` scans every `traces/split4_board*/<uuid8>/run_*/` that has a
`board_trace.jsonl` and embeds it into `data.js` (a `<script>`, not a `fetch`), so unlike
the other viewers this one works from `file://` with no HTTP server. Re-run it after any
new board run. Huge tool dumps in the transcript are truncated; board notes are kept whole.
