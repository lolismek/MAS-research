# camel/ — CAMEL-style linear-pipeline MAS

A lightweight multi-agent baseline for the sweep, in its own folder (mirrors
`autogen_gc/`). It is the **LatentMem-flattened "CAMEL"**, *not* Li et al.'s
role-play CAMEL: there is no AI-User↔AI-Assistant inception-prompting dialogue.
It is a 4-agent feed-forward pipeline where each agent runs its **own internal
ReAct loop**.

```
actor_1 ──▶ actor_2 ──▶ critic ──▶ finalizer
         (edge 1)    (edge 2 = actor_2 answer + critique)
```

- **actor_1 / actor_2** — same solver prompt; actor_2 sees actor_1 (a revision pass).
- **critic** — verifies actor_2 (has tools, so it can recompute/recheck, not rubber-stamp).
- **finalizer** — merges answer + critique into the published answer; may abstain (`UNKNOWN`).

Each agent is `run_agent(...)`: model → optional tool calls → observe → … until it
stops calling tools or hits `MAX_INNER_STEPS=30` (a runaway backstop, not a budget).
Closed-book ⇒ empty tool profile ⇒ one iteration. Qwen3.6 thinks natively (the
proxy strips `<think>`), so prompts carry no CoT scaffolding.

## Layout
- `harness/tools.py` — `web_search`, `fetch_url`, `run_python` + OpenAI schemas +
  `TOOL_PROFILES` (tools are a **per-benchmark profile**, never gated on closed/open book).
- `harness/agent.py` — `run_agent`: the one inner-loop primitive (only LLM caller).
- `harness/pipeline.py` — `run_pipeline`: the 4 agents + the 2 edges.
- `harness/addons.py` — `AddOn` seam (`inject_context` / `on_turn_end`); `vanilla` = no-op.
- `harness/run_task.py` — load task → run → score (`FINAL ANSWER` + exact-match) →
  self-meter tokens from `shared/proxy/calls.jsonl` by tag → write `traces/<arm>/<id>/run_N/`.
- `tasks/smoke_tasks.json` — 2 self-contained smoke tasks (math, web).

## The add-on seam
Coordination/memory methods are the SAME `AddOn` interface; a run holds everything
constant except the layer. A linear pipeline only needs 2 hooks:
`inject_context(role, messages)` (prepend shared state before an agent's loop) and
`on_turn_end(role, result)` (capture/publish after). `vanilla` is both no-op (only
the polished output crosses an edge). The belief board / memory arms register in
`addons.get_addon`.

## Backend
Shared Tinker proxy route `/m/<tag>/v1`, model `gpt-4o` (aliased upstream to
`Qwen/Qwen3.6-35B-A3B`). The proxy must be running (`PROXY_URL`, default
`http://127.0.0.1:8744/v1`).

## Run
```
conda run -n autogen_gc python camel/harness/run_task.py --all          # both smoke tasks
conda run -n autogen_gc python camel/harness/run_task.py smoke_math      # one
```

## Viewer
Read-only trace inspector, `viewer/serve.py` — Python stdlib only, no deps, no
writes, touches nothing in the harness. Lists every run (pass/fail, final vs
expected, calls/tokens) and renders each agent's transcript: system/user/assistant/
tool messages, tool calls + outputs, and the recovered `<think>` reasoning
(pulled from `shared/proxy/raw_calls.jsonl` by tag), plus the pipeline flow with
the 2 edges labeled. Long blocks collapse via native `<details>`.
```
python camel/viewer/serve.py            # http://127.0.0.1:8770 (refresh for new runs)
CAMEL_VIEWER_PORT=9001 python camel/viewer/serve.py
```
