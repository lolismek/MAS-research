# Magentic-One reproduction (de-Bing'd WebSurfer)

Runs the **native, unmodified** Magentic-One harness (AutoGen 0.4.8, the MAST
authors' own agbench scenario packages) against `gpt-5.4-mini` behind the local
proxy — with one targeted intervention: the WebSurfer's hardcoded Bing search
backend is swapped for a CAPTCHA-free SERP at runtime, **without editing
site-packages**.

## Why the de-Bing patch exists

In `autogen_ext` 0.4.8, `MultimodalWebSurfer` hardwires Bing three ways: it's
the start page, the only `web_search` tool, and the silent fallback in
`visit_url` (any non-URL query is rewritten to a Bing search). When the
Orchestrator instructs WebSurfer to "avoid Bing, navigate directly," the agent
*cannot* comply — there is no non-Bing affordance — and Bing's CAPTCHA wall then
deadlocks the run. In the gpt-5.4-mini reproduction this was the **dominant
Magentic-One failure signature, and it is a harness artifact, not inter-agent
misalignment**. Removing it isolates whether the remaining failures are genuine
coordination failures (orchestrator never reroutes around a stuck specialist) or
just the search confound.

## How it works (`_debing/`)

- `_debing/websurfer_debing.py` — monkeypatches the installed package at runtime:
  sets `MultimodalWebSurfer.DEFAULT_START_PAGE` and wraps
  `PlaywrightController.visit_page` (the single chokepoint both search call sites
  funnel through) to rewrite `bing.com/search` URLs to the configured SERP.
- `_debing/sitecustomize.py` — auto-loaded at interpreter startup. `run_task.py`
  puts `_debing/` on the **scenario.py subprocess** `PYTHONPATH`, so the patch
  installs before any agent is built. Gated on `autogen_ext` being importable
  (unrelated interpreters skip silently); fails loud on a real patch error so a
  Bing run is never mislabeled as de-Bing'd. The conda env stays vanilla.

### Search-engine knobs (env vars)

| var | default (de-Bing'd arm) |
|-----|--------------------------|
| `WEBSURFER_SEARCH_URL` | `https://html.duckduckgo.com/html/?q={q}` |
| `WEBSURFER_START_PAGE` | `https://duckduckgo.com/` |

Use `{q}` as the URL-encoded-query placeholder. **Faithful Bing reproduction**
(original behavior) — export:

```bash
export WEBSURFER_SEARCH_URL='https://www.bing.com/search?q={q}&FORM=QBLH'
export WEBSURFER_START_PAGE='https://www.bing.com/'
```

The console log prints `[de-bing] active: search=... start=...` so every run
records which arm it used.

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
   Confirm the console log shows `[de-bing] active` with the DDG endpoint and no
   CAPTCHA deadlock. Keep test spend ≤ $5.
3. **Full set** (run yourself, under your own spend control):
   ```bash
   conda run -n magentic_v04 python reproduction/magentic/run_task.py --all --parallel N
   ```
   Then re-judge and compare fail-rate against the Bing arm: a large drop ⇒ the
   failures were the harness confound; little change ⇒ genuine coordination
   failure (the Layer-B orchestrator-reroute fix is next).

## Dependencies / notes

- Env: conda `magentic_v04` (autogen-{core,agentchat,ext}==0.4.8 + playwright
  chromium). The de-Bing patch is branch-tracked here, so it survives env
  rebuilds — nothing to re-apply.
- `task_selection/magentic_gaia_tasks.json` references original trace dirs under
  an external `mast_repo/` (gitignored) for each task's verbatim `scenario.py`;
  re-clone per the task_selection docs if absent.
- Runtime outputs (`reproduction/runs/`, `proxy/calls.jsonl`) are gitignored.
