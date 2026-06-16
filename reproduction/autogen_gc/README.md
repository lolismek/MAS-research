# AutoGen SelectorGroupChat — second MAS baseline

> ⚠️ **Current state lives in [`EXPERIMENT_LOG.md`](EXPERIMENT_LOG.md), not here.**
> This README describes the *original* 3-agent design (`selector3`: WebResearcher /
> Analyst / Verifier). The **live system is the 4-agent `split4` variant** (WebResearcher
> / Analyst / Critic / Finalizer) in `scenario_split.py`, with stall fixes the README
> predates. Where they disagree, the log wins.

A peer-topology multi-agent system, built as the topology contrast to the
Magentic-One reproduction in `reproduction/magentic/`. Same benchmark (GAIA),
same model (`gpt-4o` alias → `gpt-5.4-mini` via the proxy), same Perplexity
search API, same answer scoring — **only the coordination topology differs.**

## Why this exists

Magentic-One is a *star*: one orchestrator reads, reasons, and self-grades; the
spokes never see each other. The 13-task analysis found it structurally ~immune
to inter-agent misalignment (cat-2 ≈ 0). Hypothesis: that immunity is a property
of the **topology**, not the difficulty.

This system is a *peer round-table*. Three agents coordinate through a shared
transcript, and — crucially — **each agent does deep work privately and publishes
only one message.** The gap between an agent's rich hidden state and its lossy
published message is the only place theory-of-mind failures, MAST 2.4
(information distortion) and 2.5 (ignored input) can arise. If they show up here
but not in Magentic-One, that supports the topology hypothesis.

## Architecture

```
SelectorGroupChat                ← an LLM selector routes between 3 peers
 ├─ WebResearcher  tools=[web_search, fetch_url]   ← ONLY agent with web access
 ├─ Analyst        tools=[run_python]              ← ONLY agent that can run code
 └─ Verifier       tools=[]                        ← no tools; reviews + emits "FINAL ANSWER:"
termination = TextMention("FINAL ANSWER:") | MaxMessage(N)
```

**Capability partition (makes it genuinely multi-agent).** Each capability lives
in exactly one agent: only WebResearcher can reach the web, only the Analyst can
run code. So any task needing a fact *and* a computation **cannot** be solved by a
single agent — a handoff is structural, not hoped-for. The Verifier has **no
tools**: it cannot silently re-do the others' work, so it must rely on their
published digests and delegate gaps back to them. That reliance is exactly where
ignored-input (2.5) and accepted-distortion (2.4) become observable.

**Two-phase Verifier.** Its system prompt separates REVIEW (an explicit critique
turn — what's supported, what's unverified/inconsistent/missing) from FINALIZE
(emitting `FINAL ANSWER:` only on a later turn, once concerns are resolved). NOTE:
this is prompt-level guidance, not a hard guarantee — the LLM selector and agent
can still finalize on a first Verifier turn. A structural guarantee (review-only
first appearance) would need `GraphFlow`; not yet implemented.

**Participation is instrumented.** `run_task.py` parses the Console log into
per-agent `speaker_turns` and `tool_calls`, plus `n_agents_spoke` and a
`single_agent` flag, and writes them into `result.json` — so a run that collapsed
to one speaker is detectable, not invisible.

Each agent is an `AssistantAgent(max_tool_iterations=K)`. Within one turn it runs
an internal ReAct loop (model → tool → model → … up to K) whose tool calls/results
stay in **private `inner_messages`**; it then publishes exactly **one**
`chat_message` to the group. Verified in the installed source
(`_chat_agent_container.py` buffers only `response.chat_message` and passes that to
the next agent) — so peers never see each other's tool loops. This is the publish
bottleneck the study targets, and the property Magentic-One's star lacks.

**Web access is function tools, not a browser.** `max_tool_iterations` loops on
*tools*, and `MultimodalWebSurfer` is a separate agent that does not gain an
internal loop — so web access must be a tool. This also removes the
Playwright/Bing/CAPTCHA surface entirely. `web_search` reuses the exact Perplexity
`/search` call from the Magentic de-Bing backend. The only thing lost vs. the
browser is page *vision* (web is text-only here), handled by the task filter.

## Topology variants

Both variants share the **entire** harness (tools, proxy, scoring, task set) and
differ only in the scenario file, so a comparison isolates topology — no branch, no
forked driver. Select with `--variant`; default is `selector3`.

- **`selector3`** (`scenario_template.py`) — the original 3 agents: WebResearcher /
  Analyst / Verifier. The Verifier both reviews and finalizes.
- **`split4`** (`scenario_split.py`) — splits the Verifier into a **Critic** (reviews,
  delegates gaps, *forbidden to finalize*) and a **Finalizer** (the only agent that
  may emit `FINAL ANSWER:`). A custom termination, `CriticThenFinalize`, ends the run
  **only** when a *Finalizer* sentinel follows a *Critic* review — a premature
  sentinel (from anyone, or before any Critic turn) does not stop the chat.

Why split4 exists: the 28-trace analysis (`FAILURE_ANALYSIS.md`) found the single
Verifier finalized on its **first turn in 20/28 traces**, skipping the two-phase
review entirely — the system message was delivered intact and the mechanism worked
in 7/28, so it was an *unenforced prompt*, not a bug. `split4` makes the review
**structural**: at least one genuine Critic review provably precedes every
finalization (validated — the Critic cannot terminate; only the Finalizer can, and
only post-review). Note this fixes the *process*, not the lossy digest — the MAST 2.4
distortion cases (info dropped at the publish bottleneck) need a separate fix.

## Files

| path | role |
|---|---|
| `tools.py` | `web_search` (Perplexity `/search`), `fetch_url` (GET + BeautifulSoup text), `run_python` (subprocess) |
| `scenario_template.py` | variant **selector3**: the 3-agent SelectorGroupChat for one task; reads `config.yaml` + `prompt.txt` |
| `scenario_split.py` | variant **split4**: 4-agent (Critic + Finalizer split) with a structural review gate (see Topology variants) |
| `run_task.py` | driver: builds run dirs, tags proxy calls, parses `FINAL ANSWER:`, writes `result.json` |
| `../../task_selection/autogen_gc_tasks.json` | the 30-task set (see below) |

Runs are written to `reproduction/runs/autogen_gc/<uid8>/run_*/`
(`console_log.txt`, `result.json`, `scenario.py`, `config.yaml`, `prompt.txt`).

## Environment

Separate conda env `autogen_gc` (autogen-agentchat/core/ext **0.7.5**, ≥ 0.6.2 for
`max_tool_iterations`) + `requests` + `beautifulsoup4`. The Magentic env
`magentic_v04` (autogen 0.4.8) is left untouched — the two systems are independent
baselines.

## Runbook

```bash
# 1. proxy must be up (chat.completions -> Perplexity /responses), port 8744
conda run -n base python reproduction/proxy/server.py &

# 2. run one / several / all tasks (default variant = selector3)
conda run -n autogen_gc python reproduction/autogen_gc/run_task.py 0383a3ee
conda run -n autogen_gc python reproduction/autogen_gc/run_task.py --all
conda run -n autogen_gc python reproduction/autogen_gc/run_task.py --all --parallel 4

# 3. run the topology variant (4-agent Critic/Finalizer split)
conda run -n autogen_gc python reproduction/autogen_gc/run_task.py --all --variant split4 --parallel 4
```

Results are namespaced by variant: `runs/autogen_gc/<variant>/<uid8>/run_*`, and
each `result.json` carries a `variant` field, so A/B is a slice by `variant`.

### Knobs (env vars)
| var | default | effect |
|---|---|---|
| `MAX_TOOL_ITERATIONS` | 8 | internal ReAct depth K per agent turn (the "private session" depth) |
| `MAX_MESSAGES` | 30 | outer-chat message cap before forced stop |
| `WEBSURFER_MAX_RESULTS` | 10 | results per `web_search` |
| `FETCH_MAX_CHARS` | 8000 | `fetch_url` truncation |
| `RUN_PYTHON_TIMEOUT` | 30 | `run_python` subprocess timeout (s) |
| `TASK_TIMEOUT` | 1800 | per-task wall-clock cap (s) |
| `PROXY_URL` | `http://127.0.0.1:8744/v1` | proxy base |

## Task set (`autogen_gc_tasks.json`)

**28 GAIA tasks, 8 L1 / 15 L2 / 5 L3** — hard by construction: **26 of 28 were
*failed* by the original Magentic-One run.** Each task carries a `category` field
so results can be sliced by the coordination dynamics it actually exercises:

| `category` | n | what it forces | why it's in the set |
|---|---|---|---|
| `web_compute` | 14 | a web fact **and** a computation on it → WebResearcher→Analyst→Verifier | the inter-agent core: the only tasks that force info to cross the partition |
| `web_only` | 12 | a web fact the Verifier must judge → WebResearcher→Verifier | thinner 2-agent ToM surface (where the `023e9d44` groupthink lived) |
| `compute_only` | 2 | computation alone → Analyst→Verifier | deliberate **single-agent control** — inter-agent failures should be ~absent here |

Curation rationale (this system is **text + web + code, no vision**):
- **Dropped** tasks the toolset literally cannot do — anything gated on reading an
  image, a video, or audio (e.g. `0e9e85b8` text-in-image, `0512426f` 360° video,
  `0bdb7c40` identify-astronaut-in-photo) — plus local audio/video/pdf/image
  attachments. A 0 on those would indict the tools, not the coordination.
- **Demoted** pure-compute tasks to a 2-task control: they're effectively
  single-agent (only the Analyst acts) and don't exercise inter-agent dynamics.
- **Topped up** `web_compute` with 8 hard `success=False` tasks from the 165-pool
  (e.g. `f0f46385` ASEAN furthest capitals = Wikipedia coords *then* pairwise
  distance; `a26649c6` chinstrap penguins = two web sources *then* a per-pair
  difference) — the configuration most likely to surface real handoff behavior.

A few `web_compute`/`web_only` tasks lean on JS-heavy or paywalled sites
(ScienceDirect `0b260a57`, data via `data.census.gov`, some PDFs); `fetch_url` is a
plain GET, so those are tool-risky but not impossible (Perplexity search often
surfaces the fact). The study cares about coordination behavior on hard tasks, not
the pass rate.

## Scoring

Identical to the Magentic harness: the last `FINAL ANSWER: <x>` line in
`console_log.txt` is captured and compared to the gold answer under `norm()`
(lowercase, strip whitespace, drop `,$%`). `result.json` schema:
`{uuid, variant, run, rc, seconds, level, category, final_answer, expected_answer,
exact_match, original_success, speaker_turns, tool_calls, n_agents_spoke,
single_agent}`.
Strict exact-match understates substantive correctness (same normalizer caveats as
the Magentic run) — read traces, not just the score. The last four fields are the
participation instrumentation: `speaker_turns`/`tool_calls` are per-agent dicts,
`n_agents_spoke` counts distinct non-user speakers, and `single_agent` flags a run
that collapsed to one speaker (a degenerate, not-really-multi-agent run).

## Caveats for comparison
- **Framework version delta** vs. Magentic-One (0.7.5 vs 0.4.8): acceptable —
  separate systems, each its own baseline; the model already differs from the
  original GPT-4o traces.
- **1 try/task is noisy** — batch ownership and try-count are set at run time.
- AutoGen is in maintenance mode (Microsoft → Agent Framework) but remains the
  widely-cited baseline.
