# Shared "thinking memory" board (`--shared-memory`)

A plug-and-play shared scratchpad for the `split4` SelectorGroupChat: each participant
maintains a slice of free-form notes that capture its **in-process reasoning**, and
every participant reads everyone's latest notes. **Off by default**; when off, the run
is behaviorally identical to the `split4` baseline.

> Status: implemented and **smoke-validated** (see *Validation* below). The full A/B over
> the 28-task set is a deliberate, separate run (owned by the experimenter), not done here.

## Why

Across the 3-MAS analysis (Magentic-One, ChatDev, AutoGen GC) the recurring failure that
*more review cycles do not fix* is **transmission of in-process reasoning**: an agent
computes or suspects the right thing inside its private tool-loop, then discards it or
publishes a lossy digest, so teammates never see it. Canonical case `72c06643` (Freon):
an agent computed ~54 mL (gold 55), discarded it, and published a bare `213→225` loop;
the Critic correctly flagged "no computation shown" because the reasoning lived only in
the private loop. Others: `3cef3a44` (basil caveat known but withheld), `48eb8242`
("internally suspicious but never says it"), `08cae58d` ("could have exposed more
reasoning"). End-of-turn prompting can't recover a thought that's already gone — capturing
it **while the agent works** can.

## What it does

- **One slice per agent** (WebResearcher, Analyst, Critic, Finalizer). All four agents read
  **and** write. The **Selector reads** the board (its routing is informed by everyone's
  current notes) but **writes nothing** — this keeps it simple and keeps the selector arm a
  clean "does letting the selector see the team's notes improve routing?" test (no rationale
  elicitation, so no CoT confound).
- **Notes are free-form** (no schema). The tool docstrings *suggest* "what I now believe /
  what I tried that failed / what I'm stuck on" but enforce nothing.
- **Append by default; revise only when a prior note became FALSE.** `add_note` appends;
  `revise_note(note_id, text)` supersedes a specific note (the old one is kept in history,
  hidden from the active view). Earlier reasoning stays visible on purpose.
- **Read at turn start** — the rendered board is injected into each participant's context
  before it acts (and re-rendered fresh on every internal inference, so mid-loop writes are
  visible). The board never replaces the agent's posted message.

## Design decisions (intentional, see git history / the design discussion)

1. Open-ended free-form notes (epistemic suggestions, not a schema).
2. Append-by-default / revise-only-when-false (stable ids; history preserved).
3. Self-authored — agents/selector write their own notes; **no side extractor model**.
4. Tool-only auto-trigger for v1 (the agent decides when to write). No forced per-tool-round
   "beat" yet — add one only if the board comes up sparse (`board_note_count` measures it).
5. All 4 agents write; all read. The **selector only reads** (it writes nothing).
6. One guardrail only: a per-author active-note cap (bounds context).

## Mechanism (files)

- **`board.py`** (new) — `Note`, `Board` (per-author notes, stable `"<Agent>-<n>"` ids,
  append/revise-with-history, per-author cap, append-only event log), and
  `BoardInjectingContext`.
  - `BoardInjectingContext(UnboundedChatCompletionContext)` overrides `get_messages()` to
    **return** `[SystemMessage(rendered_board)] + base` and **never store** it. Because
    `AssistantAgent._call_llm` re-reads the context on every inference, the board is fresh
    each call and **does not accumulate** across turns (the `Memory` protocol would, since
    `ListMemory.update_context` calls `add_message` each turn). Empty board → returns `base`
    unchanged → zero added tokens. **Do not "optimize" this into `add_message`.**
- **`tools.py`** — `make_board_tools(agent_name, board)` → per-agent `add_note` /
  `revise_note` `FunctionTool`s (names set explicitly). Each returns an echo of that agent's
  current notes (with ids) so a later `revise_note` can target a real id; a bad id returns an
  explicit error listing valid ids. When a write trips the active-note cap, the return also
  names which of the author's oldest notes was archived (so the only signal isn't a later
  `revise_note` failing on the vanished id).
- **`scenario_split.py`** — all board code gated on `SHARED_MEMORY`. All 4 agents get the
  write-tools + a `BoardInjectingContext` + a `BOARD_NOTE` system-prompt addendum
  (Critic/Finalizer get a small `max_tool_iterations` so they write-then-speak). The Selector
  (when `SELECTOR_BOARD`) is a `BoardSelectorGroupChat` whose manager splices the board into
  the selector prompt so routing is informed by the notes — it **reads only, writes nothing**,
  and returns the stock "member name only" (no rationale parse). The selector subclass reaches
  into a **private** AutoGen class, so it is wrapped in `try/except` with a fallback to the
  stock `SelectorGroupChat` (agents still read/write the board on fallback), plus an eager
  factory probe so a future-version signature drift fails at construction, not mid-run. The board is dumped to `board_trace.jsonl` in a `finally`, so even a crashed run
  keeps its trace.
- **`run_task.py`** — `--shared-memory` (+ `--no-selector-board`), threaded into `run_one`;
  board namespace; `SHARED_MEMORY`/`SELECTOR_BOARD` env into the scenario subprocess; `board_*`
  fields added to `result.json` (only when on).

## Flags & experiment arms

| arm | flags | trace namespace | isolates |
|---|---|---|---|
| baseline | *(none)* | `traces/split4[_openai]/` | the current system, untouched |
| board, agents-only | `--shared-memory --no-selector-board` | `…_board_agentsonly[_openai]/` | the board among **agents** only |
| board, full | `--shared-memory` | `…_board[_openai]/` | board + the selector **reading** the board |

> **Selector arm is now clean:** the full arm's selector only *reads* the board (no rationale
> elicitation, no writes), so the only thing it adds over the agents-only arm is "the selector
> sees the team's notes when routing" — no CoT confound. The **agents-only** arm
> (`--no-selector-board`) keeps the selector fully blind to the board, isolating the board's
> effect among the agents.

## Knobs (env vars, on top of the existing harness knobs)

| var | default | effect |
|---|---|---|
| `SHARED_MEMORY` | `0` | master switch (set by `--shared-memory`) |
| `SELECTOR_BOARD` | `1` | selector **reads** the board when routing (set to `0` by `--no-selector-board` → selector is blind to the board) |
| `BOARD_NOTE_ITERS` | `3` | tool-loop budget for the no-web/code agents (Critic/Finalizer) in board mode |

Active-note cap (`MAX_ACTIVE_NOTES_PER_AGENT=8`) and per-note char cap (`MAX_NOTE_CHARS=1200`)
are constants in `board.py`. Exceeding the active-note cap archives the author's oldest note to
history (kept in `board_trace.jsonl` as an `archive` event) and the write-tool's return tells the
author; char-cap truncation is currently silent.

## Trace outputs

- **`board_trace.jsonl`** (per run dir) — the belief-evolution log: one line per
  `add`/`revise`/`archive` with `{op, agent, note_id, text, revised_from, turn, wall}`.
- **`result.json`** gains (board runs only) `shared_memory`, `selector_board`,
  `board_event_count`, `board_note_count`, `board_revise_count`, `board_authors`. Baseline
  runs are schema-identical to before.

## Validation (smoke, on `--backend openai`)

- **$0 checks (no model calls):** board logic (append, revise-when-false + history, bad-id,
  cap, render, empty→""), `BoardInjectingContext` no-accumulation, and the selector hook's
  eager probe (confirms the private-API factory on autogen 0.7.5).
- **Live full run** (`0383a3ee`, board-full): **`exact_match: True`**, 3 agents; the board
  flowed and **WebResearcher called `add_note`** ("Found the bird … as a rockhopper penguin …");
  run converged Critic→Finalizer. (This smoke predates the read-only-selector change, so it
  also shows old Selector-authored routing notes; the selector no longer writes.)
- **No-accumulation on the wire log:** 9 requests, **max 1** scratchpad block each.
- **OFF baseline intact:** runs correctly, **no `board_*` keys**, correct namespace.

## Caveats / sharp edges

- **`--backend pplx` is currently broken for *all* `split4` runs (baseline included):**
  Perplexity reserves the custom tool name `web_search` (`400 … "web_search" is reserved`).
  Use `--backend openai`, or rename the `web_search` tool in `tools.py` (e.g. `search_web`),
  which would fix both arms on pplx.
- **The proxy reads `OPENAI_API_KEY` once at startup** (`shared/proxy/server.py:60`); after
  changing `.env`, restart the proxy or it serves an empty key (`401 … API key '' `).
- **Sparse board** (agents ignore the tool) degrades to baseline (empty render = no tokens) and
  is measurable via `board_note_count`; if low, add the deferred per-tool-round beat.
- **Selector subclass is the one version-fragile piece** — gated, probed, and falls back to the
  stock selector; pinned to autogen-agentchat 0.7.5.

## Run

```bash
# board, full (selector participates)
conda run -n autogen_gc python autogen_gc/harness/run_task.py --all --variant split4 \
  --backend openai --shared-memory --parallel 6
# board, agents-only ablation
conda run -n autogen_gc python autogen_gc/harness/run_task.py --all --variant split4 \
  --backend openai --shared-memory --no-selector-board --parallel 6
# baseline (for the A/B)
conda run -n autogen_gc python autogen_gc/harness/run_task.py --all --variant split4 \
  --backend openai --parallel 6
```
