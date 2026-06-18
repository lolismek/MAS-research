# MAS evaluation — consolidated (`eval-clean`)

A clean, uniform home for the benchmarking of **three multi-agent systems (MAS)**,
gathered from scattered work on other branches. Each MAS runs behind a shared local
proxy that aliases its model to **`gpt-5.4-mini`** (via Perplexity), so the systems run
**native and unmodified** — the model endpoint is the only swap. This branch exists for
**durability**: a prior setup gitignored the run dirs and the ChatDev traces were lost,
so here the raw traces are committed as first-class content.

## The three systems

| MAS | Topology | Task set | # | Trace state | Judging method |
|---|---|---|---|---|---|
| **Magentic-One** | star (orchestrator + specialists) | GAIA | 13 run (15 selected) | committed (~63 MB) | direct trace-reading (open-ended + MAST) |
| **ChatDev** | waterfall + shared code store | MAD games/software | 15 | **LOST → regenerate** | formal MAST 14-mode LLM judge (gpt-5.5) |
| **AutoGen GroupChat** | peer round-table (selector) | GAIA | 28 | committed `split4_openai` (~9.6 MB) | per-trace verdicts + interactive viewer |

Headline results live in each MAS's `judging/` (don't restate them from memory):
- **Magentic-One** — genuine inter-agent misalignment ≈ absent (0/13 clean); failures are
  structural / single-agent (orchestrator + broken verification). Strict 1/13, substantive ~4–5/13.
- **AutoGen GroupChat** — after the stall fix: 13 correct / 9 wrong / 4 no-answer; 0 strong
  misalignment (the 4 no-answers are selector ping-pong, unfixed by design).
- **ChatDev** — prior (now-stale) judging flagged 2.4 *Information Withholding* heavily;
  to be re-confirmed after regenerating traces.

Cross-system, broad-lens (Magentic-One vs ChatDev) side-by-side: [`RELATIONAL_COMPARISON.md`](RELATIONAL_COMPARISON.md).

## Layout (uniform per MAS)

```
<mas>/
  tasks/      the exact task set the MAS was evaluated on (+ selection inputs)
  harness/    how the MAS was run (runner, scenario/config, env notes, README)
  traces/     raw run traces (committed)
  judging/    the evaluation report + the machinery that produced it
  README.md   index for this MAS
shared/
  proxy/      ONE OpenAI⇄Perplexity proxy used by all three (server + smoke tests)
  gaia_pool/  165-task GAIA reference pool (task provenance for Magentic + AutoGen)
  mast/       how to obtain the external MAST taxonomy (the ChatDev judge needs it)
```

> **Judging is heterogeneous by design.** The three MAS were evaluated with the
> methods their original studies used (Magentic & AutoGen: open-ended / per-trace
> verdicts; ChatDev: a formal 14-mode LLM judge). They are preserved as-is. ChatDev
> will be re-run and **re-judged** (its current traces were lost and its judged
> outputs are stale).

## Setup

1. `cp .env.example .env` and fill `PERPLEXITY_API_KEY` (and `OPENAI_API_KEY` for the
   AutoGen `/o/` route). `.env` is gitignored.
2. Start the proxy: `conda run -n base python shared/proxy/server.py` (listens on `:8744`).
   Sanity check: `conda run -n base python shared/proxy/smoke_proxy.py`.
3. Per-MAS conda envs: `magentic_v04` (Magentic), `chatdev_v1` (ChatDev),
   `autogen_gc` (AutoGen). See each `<mas>/harness/README.md`.

## Provenance

- **Magentic-One** + **AutoGen GroupChat** came from the `magentic-tom` branch
  (most up-to-date runs; AutoGen = the post-stall-fix `split4_openai` batch).
- **ChatDev** came from the `chatdev-magentic-eval` branch (setup + stale judging;
  raw traces were lost and will be regenerated).
- Superseded / dead-end artifacts (pre-stall-fix AutoGen analyses, the selector3
  variant, an older Magentic run) were intentionally **dropped** — recover them from
  the source branches if ever needed.
