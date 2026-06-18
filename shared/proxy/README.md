# Shared proxy — OpenAI ⇄ Perplexity bridge

A single local proxy serves all three MAS. It is the **superset** version (from
the `magentic-tom` lineage): it carries both route families the three systems
need, so there is one proxy to run, not one per MAS.

```
<MAS> (native, unmodified, says model "gpt-4o")
   │  chat.completions
   ▼
shared/proxy/server.py   (localhost:8744)
   ├── /t/<tag>/v1/...  → Perplexity  /v1/responses   (no reasoning summaries)
   └── /o/<tag>/v1/...  → OpenAI-direct                (reasoning summaries captured)
                          model alias  any → openai/gpt-5.4-mini
```

- **Model alias**: every requested model name is aliased to `openai/gpt-5.4-mini`,
  so native ChatDev / AutoGen configs keep saying `gpt-4o` (tiktoken / model_info
  tables stay valid) with zero patches.
- **Tagged routes** (`/t/<tag>/` and `/o/<tag>/`) stamp every wire call with `<tag>`
  so calls are attributable per task/run even under parallel execution.
- **`/t/` vs `/o/`**: `/t/` = Perplexity (the default for ChatDev + Magentic);
  `/o/` = OpenAI-direct, used by the AutoGen `split4_openai` batch because
  Perplexity hides reasoning summaries.
- **ChatDev `max_tokens` drop** (`/t/cd_*` routes only): ChatDev sets
  `max_tokens = 4096 − prompt_tokens` on every call (a stale gpt-4o-era constant in
  `camel/model_backend.py`), which starves late phases and truncates the verbose
  gpt-5.4-mini mid-line. The proxy drops the cap entirely for `cd_*`-tagged routes
  so the model-max default applies; other systems keep their cap (a non-positive
  value is still dropped to avoid a fatal 400 loop). See
  `../../chatdev/judging/README.md` (confound "A"). The fix lives here, not in
  ChatDev source, so the system under test stays unmodified.

## Run

```bash
# fill repo-root .env first (PERPLEXITY_API_KEY required; OPENAI_API_KEY for /o/)
conda run -n base python shared/proxy/server.py        # listens on :8744
conda run -n base python shared/proxy/smoke_proxy.py   # 7-test sanity check
conda run -n base python shared/proxy/probe_api.py     # raw upstream API shapes
```

## Logs (gitignored)

`server.py` appends every call to `calls.jsonl` (tokens + cost summary) and the
full request/response to `raw_calls.jsonl`. Both are **gitignored** (large, and
may embed prompt/response content). The committed analysis products
(verdicts, `viewer_postfix/traces.json`) already embed what's needed; the raw
dumps are only required to *re-derive* analysis from scratch.
