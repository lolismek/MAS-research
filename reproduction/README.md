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
