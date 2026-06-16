# split4_openai — per-trace failure analysis + viewer

A second pass of the split4 trace analysis, run on the **OpenAI-direct** batch
(`runs/autogen_gc/split4_openai/`, 28 tasks, GPT-5.4-mini at effort=low) instead of
the Perplexity batch. The thing this batch uniquely has — and the Perplexity one does
NOT — is **reasoning summaries**: the private pre-action thinking each agent emitted
before every tool call / publish. The whole pipeline is built to expose the gap between
that private reasoning and the single message each agent actually published.

## Pipeline
1. **`../autogen_gc/analysis_openai/build_inputs.py`** — the openai runs have no
   `wire_log.jsonl`; every model call lives in `proxy/raw_calls.jsonl` keyed by
   `tag = agc_split4_openai_<uid8>_run<N>`. This reconstructs each run's
   SelectorGroupChat timeline (selector → private ReAct loop → one published message),
   emitting ordered **rounds** = `reason → act/publish` so each reasoning summary is
   attached to the tool call it preceded. One trace per task = its latest run.
   → `analysis_openai/inputs/<uid8>.json`
2. **`../autogen_gc/analysis_openai/render_md.py`** — renders each bundle to a compact
   markdown transcript a single subagent can read in one pass.
   → `analysis_openai/inputs_md/<uid8>.md`
3. **One analysis subagent per trace** (28 total), each following
   `analysis_openai/ANALYST_INSTRUCTIONS.md`: apply the **MAST taxonomy** first, then an
   **open-ended** precise-failure-point diagnosis, then a **required reasoning-vs-published**
   analysis (info distortion 2.4, ignored input 2.5, reasoning/action mismatch 2.6, ToM
   failures, false trust / verification theater, unreflective publishing, selector
   misrouting). Each writes `analysis_openai/verdicts/<uid8>.json`.
4. **`build_traces.py`** — merges the timelines (with reasoning) + verdicts into
   `traces.json`, sorted most-interesting-first (strong→none misalignment).
5. **`index.html`** — the viewer.

## Run the viewer
```
cd reproduction/viewer_openai && python3 -m http.server 8012
# open http://localhost:8012/
```

## Using it
- **Sidebar**: aggregate counts + one row per trace (outcome / misalignment / category·L).
- **Main**: the task, gold-vs-final, then the verdict — **primary cause**, MAST codes,
  *"What the task asks (read me first)"* (so you can judge without knowing the task),
  *how the trace went*, the *reasoning-vs-published gap*, open-ended diagnosis, MAST
  rationale, misalignment types, key failure points, key evidence.
- **Group chat**: click any message bubble → drawer showing that agent's **private ReAct
  loop**: each round's 💭 reasoning summary, its tool calls + results, and the published
  message. Click a 🧭 selector chip → the selector's own reasoning + the routing context.

## Headline result (28 traces)
- outcome: 19 no_answer · 5 correct · 3 wrong · 1 infra
- genuine inter-agent misalignment: **1 strong, 1 moderate, 16 weak, 10 none**
- dominant failure: **structural non-convergence (16/28)** — the selector keeps re-picking
  WebResearcher and never routes to the Finalizer, so the run hits the message cap with no
  `FINAL ANSWER`. MAST signature: 1.5 (unaware of termination) ×20, 1.3 (step repetition)
  ×16, 3.2/3.1 dominant. The genuine-misalignment codes (2.4/2.5/2.6) appear but are
  secondary — consistent with the Magentic finding that genuine inter-agent misalignment
  is largely *absent*; most "weak" tags are ToM/appeasement flavor on top of structural loops.
- recurring micro-pattern worth a look: WebResearcher misreads the Critic's *"stop here so
  they can address it"* as a **user stop-command** and loops "Understood — I'll stop here"
  (0ff53813, 48eb8242, de9887f5, e29834fd) — a real theory-of-mind failure.
