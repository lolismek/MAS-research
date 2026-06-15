# AutoGen SelectorGroupChat — second MAS baseline

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

## Files

| path | role |
|---|---|
| `tools.py` | `web_search` (Perplexity `/search`), `fetch_url` (GET + BeautifulSoup text), `run_python` (subprocess) |
| `scenario_template.py` | the 3-agent SelectorGroupChat for one task; reads `config.yaml` + `prompt.txt` |
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

# 2. run one / several / all tasks
conda run -n autogen_gc python reproduction/autogen_gc/run_task.py 0383a3ee
conda run -n autogen_gc python reproduction/autogen_gc/run_task.py --all
conda run -n autogen_gc python reproduction/autogen_gc/run_task.py --all --parallel 4
```

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

30 GAIA tasks, **8 L1 / 14 L2 / 8 L3** — weighted toward the hard end.
- **12 reused** (the attachment-free tasks already run on Magentic-One, for
  apples-to-apples comparison) + **18 added** harder L2/L3 from the 165-task pool.
- **Doability filter** (this system is text + web + code, no vision): excludes
  tasks needing a modality the tools lack — local audio/video/pdf/image
  attachments, and the L3 YouTube-transcription task `00d579ea`. Some remaining
  hard tasks may still be unsolvable by the toolset; that is expected (the study
  cares about coordination behavior on hard tasks, not only the pass rate).

## Scoring

Identical to the Magentic harness: the last `FINAL ANSWER: <x>` line in
`console_log.txt` is captured and compared to the gold answer under `norm()`
(lowercase, strip whitespace, drop `,$%`). `result.json` schema:
`{uuid, run, rc, seconds, level, final_answer, expected_answer, exact_match,
original_success, speaker_turns, tool_calls, n_agents_spoke, single_agent}`.
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
