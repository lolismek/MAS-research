# duet trace viewer

A single self-contained HTML page for eyeballing every smoke run — prompts, thinking
traces, tool turns, edge payloads, the shared store, and a per-run **architecture
invariant** board that proves the topology's hygiene held in the actual run (not just
in the offline prompt-diff audit).

## Build & open

```
python duet/viewer/build.py          # -> duet/viewer/index.html  (reads duet/traces/**)
open duet/viewer/index.html          # or: python -m http.server -d duet/viewer
```

`index.html` is regenerable and gitignored; rebuild it after new runs. Nothing is
fetched at view time — all traces are embedded, so it works offline / from `file://`.

## What you see per run

- **Header + metrics**: outcome, final vs expected, topology axes (relay shifts /
  hub subqs+degenerate+followup / dialogue turns+proposals+contests+ratified), tokens,
  cost, note-yield, arm_stats.
- **🏗 architecture invariants** (computed at build time off the stored message arrays):
  - `orchestrator is tool-less` — hub orchestrator made 0 tool calls (plans/merges only).
  - `worker blindness (spatial asymmetry)` — no worker's context carried another worker's
    *distinct* `<assignment>` or the merge's `<worker_reports>` layer.
  - `relay context reset (temporal asymmetry)` — each successor got a fresh context;
    only the hand-off note crossed the edge (for `full`, the inverse: the raw transcript
    is expected to cross).
  - store checks: `board`/`extract` render `<shared_record>` downstream when beliefs were
    written; `board_inert` **never** renders it; `full` renders the prior transcript.
  - `orchestrator plan is non-redundant` — **warn** (not a hygiene violation) when the
    decompose emitted duplicate sub-questions.
- **Edge artifacts & shared state**: hand-off notes, worker reports, orchestrator plan,
  peer messages, belief ledger (`store.json`), and the process judge output.
- **Agent transcripts**: one collapsible box per agent (shift / orchestrator / worker /
  peer). Each message shows its role; assistant turns expose 💭 thinking (recovered CoT),
  🔧 tool calls (name + args), and tool results. System prompts are collapsible.

Highlighting: `FINAL ANSWER:` (green), line sentinels `SUBQ:/FINDINGS:/VERDICT:/BELIEF:/…`,
injected delimiters `<task>/<assignment>/<shared_record>` (purple), and truncation
markers (red).

## Filters

topology · arm · bench · outcome · **💭 thinking** (only runs with captured CoT) ·
**✗ failing check** (only runs with a red invariant) · task-id search.

> Thinking traces exist only for runs made after the proxy was restarted with the
> `<think>`-capture tweak (Jul 1). Older traces show 💭 = none; re-run the cell to
> capture CoT.
