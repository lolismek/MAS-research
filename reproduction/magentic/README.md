# Magentic-One reproduction (real search-API WebSurfer)

Runs the **native, unmodified** Magentic-One harness (AutoGen 0.4.8, the MAST
authors' own agbench scenario packages) against `gpt-5.4-mini` behind the local
proxy — with one targeted intervention: the WebSurfer's search backend is
swapped from *browser-scraped Bing* to a real **search API** (Perplexity
`/search`) rendered into a clean local results page, at runtime, **without
editing site-packages**.

## Why this exists

In `autogen_ext` 0.4.8, `MultimodalWebSurfer` does **not** call a search API. Its
`web_search` tool (and the `visit_url` query fallback) navigate the live browser
to `https://www.bing.com/search?q=...` and read the rendered HTML via
screenshot + set-of-mark. That is *scraping a consumer search engine* — exactly
what trips bot-detection: a headless Chromium from a datacenter IP hits Bing's
CAPTCHA wall and the run deadlocks. In the gpt-5.4-mini reproduction this was the
**dominant Magentic-One failure signature, and it is a harness artifact, not
inter-agent misalignment**.

The earlier de-Bing (rewrite the Bing URL to a DuckDuckGo *HTML* SERP) only
traded one scraped consumer SERP for another — it still bot-walled and still
leaked (the agent reached Bing via an in-page search box). The honest fix is to
**stop scraping search engines altogether**: call a proper search API that
returns structured JSON and feed the agent a clean, JS-free results page.

## How it works (`_debing/`)

`_debing/websurfer_debing.py` monkeypatches the installed package at runtime:

1. **`MultimodalWebSurfer.__init__`** is wrapped so `self.start_page` is forced
   to a clean local home page. The agent never lands on bing.com, so it can
   never type into Bing's in-page search box (the leak the URL-rewrite had).
   (Patching `DEFAULT_START_PAGE` alone is not enough: the `__init__` default is
   bound at class-definition time and `_lazy_init` `goto()`s the start page
   directly, bypassing `visit_page`.)
2. **`PlaywrightController.visit_page`** — the single chokepoint both search call
   sites funnel through — intercepts any `bing.com` navigation. A search URL
   (`/search?q=...`) triggers a Perplexity `/search` API call; the JSON results
   are rendered into a clean local HTML SERP (`file://`) and the browser is
   pointed at *that*. Any other bing.com URL (homepage, etc.) → the local home
   page.

**Nothing else changes.** The agent still screenshots the page, set-of-mark
still tags the result links, and clicking a result still navigates the real
browser to the real URL. So **no prompt or orchestrator change is needed** — the
agent's mental model ("I searched, I see results, I click one") is preserved
exactly; only the *source* of the results page changes. Normal page visits
(Wikipedia, etc.) still hit the real browser — only *search* is replaced, since
search engines are the bot-walled chokepoint, not content pages.

`_debing/sitecustomize.py` is auto-loaded at interpreter startup. `run_task.py`
puts `_debing/` on the **scenario.py subprocess** `PYTHONPATH`, so the patch
installs before any agent is built. Gated on `autogen_ext` being importable
(unrelated interpreters skip silently); fails loud on a real patch error so a
Bing run is never mislabeled. The conda env stays vanilla.

### Knobs (env vars)

| var | default | meaning |
|-----|---------|---------|
| `WEBSURFER_SEARCH_BACKEND` | `perplexity` | `perplexity` (API → clean SERP) or `bing` (passthrough: original scraped-Bing arm, for A/B) |
| `WEBSURFER_MAX_RESULTS` | `10` | results per SERP |
| `WEBSURFER_START_PAGE` | local home page | override the start page |
| `PPLX_SEARCH_URL` | `https://api.perplexity.ai/search` | search API endpoint |
| `PERPLEXITY_API_KEY` | from env / repo-root `.env` | key for the search API |

The console log prints `[search-backend] active: ...` (or `passthrough: native
scraped Bing`) so every run records which arm it used. Each run's queries +
result counts are logged to `search_calls.jsonl` in the run's temp SERP dir.

**Faithful original reproduction** (scraped Bing, will CAPTCHA-deadlock):

```bash
export WEBSURFER_SEARCH_BACKEND=bing
```

## Runbook

1. **Proxy** (translates chat.completions ↔ Perplexity Responses; needs
   `PERPLEXITY_API_KEY` in a repo-root `.env`):
   ```bash
   conda run -n base python reproduction/proxy/server.py   # listens on :8744
   ```
2. **Smoke (1 task)** — `5a0c1adf` is the canonical Bing-loop case (Malko
   conducting competition):
   ```bash
   conda run -n magentic_v04 python reproduction/magentic/run_task.py 5a0c1adf
   ```
   Confirm the console log shows `[search-backend] active: perplexity ...`, zero
   `bing.com` landings, and zero CAPTCHA mentions. Keep test spend ≤ $5.
3. **Full set** (run yourself, under your own spend control):
   ```bash
   conda run -n magentic_v04 python reproduction/magentic/run_task.py --all --parallel N
   ```
   Then re-judge and compare fail-rate against the `WEBSURFER_SEARCH_BACKEND=bing`
   arm: a large drop ⇒ the failures were the harness confound; little change ⇒
   genuine coordination failure (the Layer-B orchestrator-reroute fix is next).

## Dependencies / notes

- Env: conda `magentic_v04` (autogen-{core,agentchat,ext}==0.4.8 + playwright
  chromium). The patch is branch-tracked here, so it survives env rebuilds —
  nothing to re-apply.
- `task_selection/magentic_gaia_tasks.json` references original trace dirs under
  an external `mast_repo/` (gitignored) for each task's verbatim `scenario.py`;
  re-clone per the task_selection docs if absent.
- Runtime outputs (`reproduction/runs/`, `proxy/calls.jsonl`) are gitignored.
