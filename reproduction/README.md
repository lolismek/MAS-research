# Native reproduction harness: ChatDev 1.0 + Magentic-One on gpt-5.4-mini

Both MAS run with their **native tooling, unmodified** — the only swap is the
model endpoint, behind a local proxy. Both control tasks validated end-to-end
on 2026-06-10 (combined smoke+control cost: ~$0.26).

## Architecture

```
ChatDev v1.1.6 (openai SDK) ──────────────┐
                                          │  /v1/chat/completions
Magentic-One (autogen 0.4.8,              ├──> proxy/server.py ──> Perplexity
  OpenAIChatCompletionClient) ────────────┘       (localhost:8744)   /v1/responses
                                                                     openai/gpt-5.4-mini
```

`proxy/server.py` translates chat.completions <-> Responses API (Perplexity
serves gpt-5.4-mini ONLY via /v1/responses; chat.completions is Sonar-only).
It aliases any requested model name to `openai/gpt-5.4-mini`, so native
configs keep saying `gpt-4o` — which keeps ChatDev's tiktoken/ModelType tables
and AutoGen's model_info (vision+function_calling) working with zero patches.
Tool calls round-trip; **images pass through and work** (verified: Perplexity
gpt-5.4-mini accepts `input_image`; the 2026-06-06 "no vision" finding no
longer reproduces) — so MultimodalWebSurfer browses with real screenshots,
fully native. Every call is logged to `proxy/calls.jsonl` with tokens + exact
cost. Smoke tests: `proxy/smoke_proxy.py` (7/7 pass), raw API shapes:
`proxy/probe_api.py`.

Start: `conda run -n base python reproduction/proxy/server.py`

## ChatDev 1.0

- Code: `chatdev_repo/` = OpenBMB/ChatDev at tag **v1.1.6** (2024-11-12, last
  1.x release — the MAST run window; main branch is now the 2.x rewrite).
  Gitignored; re-clone + `git checkout v1.1.6`.
- Env: conda `chatdev_v1` (py3.10, `pip install -r requirements.txt` then
  `pip install httpx==0.27.2` — openai 1.3.3 breaks on httpx>=0.28).
- Run: `conda run -n chatdev_v1 python reproduction/chatdev/run_task.py <Name> [...]|--all [--parallel N]`
  (driver invokes the repo's own run.py per task with MAD project_names,
  archives the WareHouse output — code + full dialogue .log = the judge
  transcript — into `runs/chatdev/<name>/run_N/` with result.json).
- Control validated: Gomoku — full waterfall (DemandAnalysis, LanguageChoose,
  Coding, CodeReview x3, Test, EnvironmentDoc, Manual), 26 utterances, 60s,
  $0.06, compilable 3-file game.

## Magentic-One

- MAST ran it via agbench; every original trace dir ships the exact
  `scenario.py` executed (byte-identical to the agbench GAIA MagenticOne
  template at microsoft/autogen@af5dcc7, 2025-02-07, modulo per-task
  `__FILE_NAME__`). We re-execute each task's own scenario.py verbatim.
- Version pin: **autogen-{core,agentchat,ext}==0.4.8** (2025-03-04 — inside
  the window between the template commit and the MAST paper, 2025-02-07..03-13).
- Env: conda `magentic_v04` (py3.11, autogen 0.4.8 +
  `markitdown==0.0.1a3` — modern markitdown/magika breaks 0.4.8's FileSurfer —
  + `playwright install chromium`).
- Run: `conda run -n magentic_v04 python reproduction/magentic/run_task.py <uuid8> [...]|--all [--parallel N]`
  → `runs/magentic/<uuid8>/run_N/` with console_log.txt (same format as the
  originals), logs/ screenshots, result.json (FINAL ANSWER vs expected,
  normalized exact match).

## MacNet (larger-MAS extension)

- Code: `macnet_repo/` = OpenBMB/ChatDev branch **macnet**, pinned at commit
  **e7a35824fd683ffe8fc237e28ecc47d7b1a5da63** (no tags exist on the branch).
  Gitignored; re-clone with `git clone --depth 1 --branch macnet
  https://github.com/OpenBMB/ChatDev macnet_repo` and verify the SHA.
- Env: conda `macnet` (py3.10, `pip install -r requirements.txt` with
  `rich>=13` instead of the pinned 9.13 — upstream's own pins are mutually
  unresolvable (openai 1.44.1 needs typing-extensions>=4.11, rich 9.13 needs
  <4) — then `pip install httpx==0.27.2`, same openai-1.x/httpx-0.28 breakage
  as chatdev_v1). `imgcat` comes from requirements (PyPI CLI); `dot` from
  Homebrew graphviz. Endpoint: same `BASE_URL` env mechanism as ChatDev.
- Configs (system name = `macnet-<config>` in runs/ and judged/):
  - `chain`: 10 nodes in a line, the 15 chatdev_tasks.json prompts (max
    solution handoffs);
  - `mlp`: 8 nodes in dense layers (4-2-2, complete bipartite between
    consecutive layers), same prompts — redundancy arm with WORKING
    aggregation (see the `net` note below for why mlp and not net);
  - `net`: 8 nodes, complete DAG (28 edges), same prompts — OPTIONAL /
    exploratory only, see deviation note 8;
  - `rand`: 10 nodes, seeded TRUE random DAG (RAND_SEED=7 in run_task.py,
    one fixed sample shared by all tasks/runs: 18 edges including skip
    edges, 9 execution steps, fan-ins up to 3; edge list recorded in each
    result.json). **The single-topology arm of choice**: irregular,
    non-layered topology mixing plain handoffs with genuine aggregation at
    7 merge points (nodes 4, 5, 6, 7, 8, 9 and the output collector).
    Depends on the scheduler patch of deviation note 11 — unpatched, every
    skip edge degenerates into `net`'s silent first-solution fallback.
    MacNet's own `generate_random` is NOT used: no connectivity guarantee
    (isolated nodes possible) and edge count sampled up to n(n-1)/2 (cost
    hazard); the driver samples a backbone-connected DAG with total edges
    bounded in [1.5n, 2n) instead;
  - `srdd`: 10-node chain on `task_selection/macnet_srdd_tasks.json`
    (MacNet's native benchmark; personas via `--type <category>`).
- Run: `conda run -n macnet python reproduction/macnet/run_task.py
  --config chain|mlp|net|rand|srdd <Name> [...]|--all [--parallel N]`.
  MacNet reads config.yaml/MacNetLog/WareHouse cwd-relative and re-reads
  config.yaml mid-run, so the driver gives every run a private copy of
  macnet_repo (deleted after archiving). The driver writes the `graph:` edge
  list into config.yaml directly (byte-identical to what the repo's
  generate_graph.py emits, minus its imgcat/graphviz detour).
- Trace for the judge: `runs/macnet-<cfg>/<slug>/run_N/trace.log` = MacNet's
  own MacNetLog transcript (Original Solution / Suggestions / Optimized
  Solution per edge + aggregation events), utf-8.

## DyLAN (larger-MAS extension)

- Code: `dylan_repo/` = SALT-NLP/DyLAN pinned at commit
  **006e440a519f7cf21e2826f3b8033d84ae9bf07c** (no releases). Gitignored.
- Env: conda `dylan` (py3.10, `openai==0.27.6 backoff pandas==1.5.3
  numpy==1.22.4 prettytable astunparse` — the repo's requirements minus
  human-eval/sacrebleu, which only the HumanEval track needs).
- Config: the paper-default MMLU setup, unmodified — 7 role agents
  (Economist, Doctor, Lawyer, Mathematician, Psychologist, Programmer,
  Historian), 3 rounds, listwise ranker activation, 2/3-consensus early
  stop (`code/MMLU/llmlp_listwise_mmlu.py`).
- Endpoint: openai 0.x honors `OPENAI_API_BASE`; DyLAN calls with `engine=`,
  which the 0.x SDK turns into `/engines/<engine>/chat/completions` — the
  proxy routes that path family (engine name ignored, aliasing as usual).
- Tasks: `task_selection/dylan_tasks.json` — 12 items a single gpt-5.4-mini
  call gets wrong + 3 it gets right (controls), screened from 120 candidates
  across 6 hard MMLU subjects (`task_selection/screen_dylan.py`; full pool
  outcomes in `dylan_screen_results.json`; baseline failure rate 36/120).
- Run: `conda run -n dylan python reproduction/dylan/run_task.py
  <id> [...]|--all [--parallel N]` → `runs/dylan/<id>/run_N/` with
  `transcript.txt` (judge input, rebuilt from DyLAN's own per-round
  completion log: every agent reply per round + deactivation markers +
  final answer vs gold) and result.json (`final_correct` = DyLAN's own
  exact-match bookkeeping).

### DyLAN MATH arm (`dylan-math`)

Added after the MMLU batch ran: 13/15 MMLU items early-stopped at round 1
with ~5 calls — on 4-option multiple choice, individually-wrong agents
collide on the same letter often enough to trigger the 2/3 consensus, so
traces carried almost no inter-agent dynamics. The MATH track uses free-form
`\boxed{}` answers graded by the framework's own `is_equiv`, so consensus
requires genuine convergence.

- Config: `code/MMLU/llmlp_listwise_math.py` (same LLMLP machinery, qtype
  `math_exp`), 7 agents = one specialist per Hendrycks MATH subject from the
  repo's own `ROLE_MAP_MATH` (AlgebraExpert, CountingProbabilitySpecialist,
  GeometryWizard, IntermediateAlgebraMaestro, NumberTheoryScholar,
  PrealgebraProdigy, PrecalculusGuru). The paper's MATH experiments used 4
  agents; the 7-specialist team is a deliberate deviation to keep team size
  identical to the MMLU arm and maximize judge-visible interaction.
- Tasks: `task_selection/dylan_math_tasks.json` — 12 baseline failures + 3
  controls from the 134 level-5 items of HuggingFaceH4/MATH-500
  (`task_selection/screen_dylan_math.py`; pool outcomes in
  `dylan_math_screen_results.json`; baseline failure rate 38/134 after
  excluding one formatting-only `is_equiv` false negative, which is
  reclassified and barred from selection — run-time grading would be
  equally unreliable on it).
- Run: `conda run -n dylan python reproduction/dylan/run_math_task.py
  <id> [...]|--all [--parallel N]` → `runs/dylan-math/<id>/run_N/`, same
  artifact layout as the MMLU arm (the runner writes each problem as a
  one-file Hendrycks-format dir, since the script loads MATH problems from
  per-file JSON).
- Batch result (2026-06-11, $0.77 for 141 calls): 8/15 exact-match correct
  by the framework's own is_equiv; 4 runs went the full 3 rounds (17 calls)
  — the multi-round debate traces the MMLU arm lacked.
- **Outcome corrections from judging + trajectory analysis** (see
  `reproduction/dylan/analyze_trajectories.py` and the judged records):
  - Two "failures" are is_equiv grading artifacts, for DyLAN *and* for the
    screening baseline (`algebra_2626`: `32348` vs gold `\$32,\!348`;
    `intermediate_algebra_1388`: unordered set `-2,1` vs gold `1,-2`).
    Corrected: DyLAN 10/15 semantically correct; 10 genuine baseline
    failures, of which 5 fixed.
  - Of the 5 genuine unfixed failures, **3 are structural losses, not
    capability failures**: agents derived the correct answer but the system
    lost it. Mechanism: the debate prompt demands an updated answer AND 1-5
    peer scores "in the form like [[1, 5, 2, ...]]" in the same reply,
    while ans_parser (extract_math_answer) records the LAST \boxed{}
    expression — agents that box their scores after their answer get the
    score matrix recorded as their "answer", and consensus/final selection
    then operate on garbage (`counting_525`: all 7 agents converged on the
    correct 144 in round 2, final answer `[[5,5,5,5,5,5,5]]`;
    also `intermediate_algebra_1197`, `prealgebra_1646`). Only 2 failures
    (`geometry_880`, `precalculus_768`) are pure capability (no agent ever
    had the right answer). This is native framework behavior, not a
    reproduction bug.

## Parallelism & trace attribution

Every run is an isolated subprocess in its own directory; the proxy is
stateless and threaded, so tasks parallelize freely (`--parallel N`). Each run
hits a tagged proxy route (`/t/<tag>/v1/chat/completions`), and the tag is
stamped on every calls.jsonl and raw_calls.jsonl entry — wire traffic stays
fully attributable under concurrency (validated: Pong + ConnectFour in
parallel, 15/14 calls cleanly separated). raw_calls.jsonl is the ground-truth
dump of every model request/response (images as sha1 stubs matching logs/
PNGs); it captures model-internal turns that never reach console logs, e.g.
the Magentic orchestrator's progress-ledger JSON. Suggested N: 3-4 (chromium
memory + Perplexity rate limits; proxy retries 429s with backoff).
- Control validated: 0383a3ee (L1) — 277s, WebSurfer browsed with real
  screenshots (43 image-bearing calls), FINAL ANSWER "rockhopper penguin" =
  expected, exact_match true (original GPT-4o also succeeded).

## Deviations from the original MAST setup (complete list)

1. Model: gpt-4o -> gpt-5.4-mini behind the alias (the experiment variable).
2. Magentic-One code executor runs on the host, not in agbench's Docker
   container (scenario.py itself is identical; LocalCommandLineCodeExecutor is
   the same class). Consider Docker for the full sweep if generated code needs
   isolation.
3. Responses API is stateless (no server-side conversation state) — semantics
   identical since chat.completions resends full history anyway.
3b. Proxy drops `max_tokens` when ChatDev computes it <= 0 (its hardcoded
   4096-token gpt-4o budget minus a too-long prompt; gpt-5.4-mini writes
   longer code than GPT-4o, so review prompts outgrow the budget more often).
   Original behavior would be a fatal 400-retry loop, i.e. an infra crash,
   not a research-relevant failure mode.
4. GAIA web drift: answers are time-anchored to ~2024; judge pass must
   separate web-decay failures from coordination failures (noted in
   task_selection/README.md).
5. MacNet logging patch (macnet_repo/graph.py, one line, marked
   `[reproduction patch]`): the log FileHandler's `encoding="gbk"` →
   `"utf-8"`. Upstream's gbk handler silently DROPS every log record that
   contains a non-GBK character (emit() swallows the UnicodeEncodeError), so
   the transcript the judge reads would be incomplete. Logging-only; agent
   behavior untouched.
6. MacNet env: `rich>=13` instead of the pinned 9.13 (upstream
   requirements.txt is internally unresolvable, see MacNet section). rich
   only renders console boxes/diffs; the .log transcript is unaffected.
7. Proxy addition (infra, not framework): `/engines/<engine>/chat/completions`
   route family for openai-0.x `engine=` calls (DyLAN). Same handler,
   engine ignored.
7b. Proxy translation guard: chat messages with empty string content are
   forwarded as a single space. OpenAI chat.completions accepts
   `content: ""` but Perplexity Responses rejects it ("content cannot be
   empty"); MacNet's aggregation step (chatdev/waiting.py) sends such a
   message, which would otherwise 400-loop and crash the run — an infra
   mismatch, not a research-relevant failure.
8. MacNet `net` topology has structurally inert aggregation at the pinned
   commit (upstream behavior, NOT patched): the layered executor deletes
   consumed predecessor edges after each layer, and aggregation requires
   `len(pre_solutions) == len(remaining predecessors)` — for complete-DAG
   inputs arriving across layers this almost never holds, so
   multi-predecessor nodes log "insufficient predecessors" and silently
   fall back to their FIRST received solution, discarding the rest.
   Verified empirically (net n=3 smoke: zero aggregation events; the
   layer-3 node's solution.txt hash-matches its first pre_solution while
   the later, larger contribution is dropped). Topologies whose inputs
   arrive within ONE execution layer (`mlp`, `star`) aggregate correctly.
   Hence the redundancy arm uses `mlp`; `net` remains available as an
   exploratory config — its traces show architecture-induced information
   discarding (the discarded suggestions/solutions ARE in the trace, so
   the judge sees them), but it is not a working aggregation arm and costs
   ~3x chain. The same degeneration applies to MacNet's native
   `generate_random`, which is why the `rand` config uses a driver-side
   layered sampler instead.
9. MacNet truncation patch (macnet_repo/camel/model_backend.py, both API
   branches, marked `MAS-REPRO PATCH`): upstream sets
   `max_tokens = 4096 - prompt_tokens` for gpt-4o on EVERY call, so any
   rewrite or merge whose prompt contains a codebase gets its reply
   truncated (`finish=length`) — mlp n=4 smoke: 81/101 calls truncated,
   aggregations failing via retry-limit fallback. That is a systemic loss
   source that would masquerade as agent-level information withholding
   (2.4/2.5), so the patch drops the param and lets the API's
   model-maximum default apply. Errors in the traces are now attributable
   to agents, not the token budget. (The proxy's note-3b guard for <=0
   budgets stays, for ChatDev.)
10. Perplexity API drift (2026-06-12, infra): the Responses endpoint went
   schema-strict and now 400s on `store`, `temperature`, `top_p`, and
   `parallel_tool_calls` (each probed individually; `max_output_tokens`
   still accepted). The proxy no longer forwards them. CONSEQUENCE for
   MacNet: its depth-annealed temperature schedule (1 - depth/graph_depth,
   the explore->exploit gradient) is inert — every node samples at the
   model's fixed default. Applies equally to all arms run after this date;
   pre-drift runs (ChatDev, Magentic, DyLAN, all judged traces) sent
   temperature while upstream still accepted it.
11. MacNet scheduler patch (macnet_repo/graph.py, two marked `MAS-REPRO
   PATCH` sites): aggregation now compares accumulated pre_solutions
   against each node's BUILD-TIME in-degree instead of the live
   (edge-deleted, shrinking) predecessor list, so it fires exactly once —
   when the last predecessor delivers — regardless of which execution
   layer each input arrived in. Upstream's condition only ever held for
   layer-aligned arrivals (deviation note 8), making aggregation
   structurally inert for any DAG with skip edges; that is a scheduler
   artifact that would masquerade as agent-level input-ignoring (2.5).
   This patch DOES alter collaboration semantics relative to the pinned
   artifact — it implements per-node aggregation as the MacNet paper
   describes it. It also revives aggregation for the `net` config
   (previously inert; post-patch every net node merges all predecessors —
   re-estimate cost before ever running it). Validated by offline executor
   simulation + rand n=6 smoke. Layer-aligned topologies (chain, mlp,
   srdd) are unaffected: for them build-time in-degree and the upstream
   condition coincide.
12. MacNet docstring-mangle patch (macnet_repo/graph.py optimize +
   chatdev/waiting.py llm_api, marked `MAS-REPRO PATCH`): upstream rewrote
   every `'''` in model replies to `\n'''` (legacy fence normalization),
   de-indenting every Python docstring — the first rand smoke's WareHouse
   main.py was a complete, logically sound Gomoku that failed to compile
   (IndentationError) although the raw wire dump shows the agent emitted
   correct indentation. The Codes parser (chatdev/codes.py:34) only
   matches ``` fences, so the `'''` rewrite is dropped; the ```
   normalization the parser needs is kept. Without this, outcome grading
   and judge labels would blame agents for framework-corrupted artifacts.
   Note the surviving upstream quirk: replies also get `main.py` ->
   `\nmain.py` in the merge path (kept — removing it risks the filename
   regex); mid-line "main.py" mentions in strings/comments can still be
   reformatted by the framework.

Pre-batch validation runs (MacNet chain n=3 / mlp n=4 / net n=3 / rand n=6,
DyLAN control) live in `runs/_smoke/` — outside the judge's globs, kept for
reference. The rand n=6 smoke (2026-06-12, post-patches: $0.25, 245s,
36 calls all `finish=stop`, 5/5 aggregations succeeded first-try — incl.
cross-layer merges impossible pre-patch — zero retries) validates deviation
notes 9-11 end-to-end; the executor was also simulated offline to confirm
aggregation fires at every multi-indeg node of the seed-7 graph.

## Full-experiment batch commands (run these yourself — not automated)

Start the proxy first; judge afterwards. Costs are rough, observable live via
`python3 -c "import json;print(sum(json.loads(l).get('cost') or 0 for l in open('reproduction/proxy/calls.jsonl')))"`.

Proxy guardrails (2026-06-12): when a caller sends no token cap the proxy
applies `OUT_TOKEN_CAP` (default 16384 — ~6x the largest reply ever logged,
2,564 tokens; hits are auditable as `finish=length` in calls.jsonl), and it
refuses calls outright once the session's summed cost passes `SPEND_CAP`
(default $20 per proxy process — plenty for any one batch; the judge run
needs `SPEND_CAP=100 conda run -n base python reproduction/proxy/server.py`).

```bash
# 0. proxy (leave running)
conda run -n base python reproduction/proxy/server.py

# 1. MacNet rand (THE single-topology arm) on the 15 ChatDev tasks
#    (~$6-10, ~1.5-2.5h: rand n=6 smoke cost $0.25/task; the full 10-node
#    graph has ~1.6x the transmissions plus larger codebases.
#    Post-truncation-patch (deviation note 9) there are no retry storms —
#    still watch calls.jsonl after the first 2-3 runs.)
conda run -n macnet python reproduction/macnet/run_task.py --config rand --all --parallel 3

# 1b. OPTIONAL alternates, same prompts (not part of the single-topology
#     plan): chain (pure handoffs), mlp (paper-faithful dense aggregation),
#     net (inert aggregation, deviation note 8), srdd (native benchmark).
# conda run -n macnet python reproduction/macnet/run_task.py --config chain --all --parallel 4
# conda run -n macnet python reproduction/macnet/run_task.py --config mlp --all --parallel 3
# conda run -n macnet python reproduction/macnet/run_task.py --config net --all --parallel 3
# conda run -n macnet python reproduction/macnet/run_task.py --config srdd --all --parallel 4

# 4. DyLAN on the 15 screened MMLU items (~$1, ~30min)
#    [DONE 2026-06-11, $0.18 — runs/dylan/ populated, 12/15 exact match]
conda run -n dylan python reproduction/dylan/run_task.py --all --parallel 4

# 4b. DyLAN MATH arm on the 15 screened MATH level-5 items (~$1, ~25min)
#     [DONE 2026-06-11, $0.77 — runs/dylan-math/ populated, 8/15 exact match]
conda run -n dylan python reproduction/dylan/run_math_task.py --all --parallel 4

# 5. judge the new traces (dominant cost: ~$1.2/trace x 70 ≈ $85; resume-safe;
#    use --only to judge per system and watch spend between systems)
conda run -n base python reproduction/judge/judge.py --new --parallel 4

# 6. analysis + report
conda run -n base python reproduction/judge/analyze.py overview
conda run -n base python reproduction/report/make_report.py
```
