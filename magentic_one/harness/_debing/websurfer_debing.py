"""Replace the Magentic-One WebSurfer's search backend (the "honest fix").

Why this exists
---------------
autogen_ext 0.4.8 ``MultimodalWebSurfer`` does not use a search *API*. Its
``web_search`` tool (and the ``visit_url`` query fallback) navigate the live
browser to ``https://www.bing.com/search?q=...`` and read the rendered HTML via
screenshot + set-of-mark. That is *scraping a consumer search engine*, which is
exactly what trips bot-detection: a headless Chromium from a datacenter IP hits
Bing's CAPTCHA wall and the run deadlocks. In the gpt-5.4-mini reproduction this
was the dominant Magentic-One failure signature — a harness/tooling artifact,
not inter-agent misalignment.

A URL-rewrite to another *scraped* SERP (the earlier DuckDuckGo de-Bing) only
trades one bot-walled consumer SERP for another. The real fix is to stop
scraping search engines altogether: call a proper search **API** that returns
structured JSON, and feed the agent a clean results page.

What it does
------------
Monkeypatches the *installed* package at runtime (no site-packages edit):

  1. ``MultimodalWebSurfer.__init__`` is wrapped so ``self.start_page`` is forced
     to a clean local home page — the agent never lands on bing.com, so it can
     never type into Bing's in-page search box (the leak the URL-rewrite had).
  2. ``PlaywrightController.visit_page`` — the single chokepoint both search call
     sites funnel through — intercepts any ``bing.com`` navigation. A search URL
     (``/search?q=...``) triggers a Perplexity ``/search`` API call; the JSON
     results are rendered into a clean, JS-free, CAPTCHA-free local HTML SERP
     (``file://``) and the browser is pointed at *that*. Any other bing.com URL
     (e.g. the homepage) is redirected to the local home page.

The rest of the pipeline is untouched: the agent still screenshots the page,
set-of-mark still tags the result links, and clicking a result still navigates
the real browser to the real URL. So **no prompt or orchestrator change is
needed** — the agent's mental model ("I searched, I see results, I click one")
is preserved exactly; only the *source* of the results page changes.

Loaded automatically by the sibling ``sitecustomize.py`` when
``reproduction/magentic/_debing`` is on ``PYTHONPATH`` (``run_task.py`` puts it
there for the scenario.py subprocess), so the conda env stays vanilla.

Knobs (env)
-----------
  WEBSURFER_SEARCH_BACKEND  "perplexity" (default) | "bing" (passthrough; runs
                            the original scraped-Bing arm for A/B comparison)
  WEBSURFER_MAX_RESULTS     results per SERP (default 10)
  WEBSURFER_START_PAGE      override the start page (default: clean local home)
  PPLX_SEARCH_URL           default https://api.perplexity.ai/search
  PERPLEXITY_API_KEY        read from env, else loaded from the repo-root .env
"""
import html
import json
import os
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlparse

import requests

BACKEND = os.environ.get("WEBSURFER_SEARCH_BACKEND", "perplexity").lower()
PPLX_SEARCH_URL = os.environ.get("PPLX_SEARCH_URL", "https://api.perplexity.ai/search")
MAX_RESULTS = int(os.environ.get("WEBSURFER_MAX_RESULTS", "10"))
START_PAGE_OVERRIDE = os.environ.get("WEBSURFER_START_PAGE")  # None -> local home page

_applied = False
_tmpdir = None
_home_url = None
_serp_n = 0
_log_lock = threading.Lock()


def _load_key():
    """PERPLEXITY_API_KEY from env, else from the nearest ancestor .env."""
    if os.environ.get("PERPLEXITY_API_KEY"):
        return os.environ["PERPLEXITY_API_KEY"]
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        p = os.path.join(d, ".env")
        if os.path.exists(p):
            for line in open(p):
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k, v)
            break
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return os.environ.get("PERPLEXITY_API_KEY")


def _search_query(url):
    """Return the search query if `url` is a Bing search URL, else None."""
    try:
        u = urlparse(url)
    except Exception:
        return None
    host = (u.hostname or "").lower()
    if (host == "bing.com" or host.endswith(".bing.com")) and u.path.startswith("/search"):
        return parse_qs(u.query).get("q", [""])[0]
    return None


def _is_bing(url):
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host == "bing.com" or host.endswith(".bing.com")


def _pplx_search(query, key):
    r = requests.post(
        PPLX_SEARCH_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"query": query, "max_results": MAX_RESULTS},
        timeout=60,
    )
    r.raise_for_status()
    return r.json().get("results", [])


_CSS = (
    "body{font-family:Arial,Helvetica,sans-serif;max-width:760px;margin:18px;color:#202124;}"
    "h2{font-size:16px;font-weight:normal;color:#5f6368;margin:0 0 18px;}"
    ".r{margin:0 0 22px;} .t{font-size:18px;line-height:1.3;}"
    "a{color:#1a0dab;text-decoration:none;} a:hover{text-decoration:underline;}"
    ".u{color:#006621;font-size:13px;margin:1px 0;} .s{color:#3c4043;font-size:14px;line-height:1.45;}"
)


def _render_serp(query, results):
    esc = html.escape
    rows = []
    for x in results:
        url = x.get("url") or ""
        title = esc(x.get("title") or url or "(untitled)")
        snippet = esc(" ".join((x.get("snippet") or "").split()))
        rows.append(
            f'<div class="r"><div class="t"><a href="{esc(url)}">{title}</a></div>'
            f'<div class="u">{esc(url)}</div><div class="s">{snippet}</div></div>'
        )
    body = "\n".join(rows) or "<p>No results found.</p>"
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<title>Search: {esc(query)}</title><style>{_CSS}</style></head>"
        f'<body><h2>Web results for: {esc(query)}</h2>{body}</body></html>'
    )


_HOME = (
    '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Web</title>'
    f"<style>{_CSS}</style></head><body><h2>Web browser ready</h2>"
    "<p>Use the <b>web_search</b> tool to search the web, or "
    "<b>visit_url</b> to open a page directly.</p></body></html>"
)


def _write(name, content):
    path = os.path.join(_tmpdir, name)
    with open(path, "w") as f:
        f.write(content)
    return "file://" + path


def _log(kind, query, n):
    with _log_lock, open(os.path.join(_tmpdir, "search_calls.jsonl"), "a") as f:
        f.write(json.dumps(dict(ts=time.time(), kind=kind, query=query, n_results=n)) + "\n")


def apply():
    """Idempotently install the patch. Raises on failure (fail loud: a broken
    patch must abort the run, never silently fall back to scraped Bing)."""
    global _applied, _tmpdir, _home_url, _serp_n
    if _applied:
        return
    _applied = True

    if BACKEND == "bing":
        print("[search-backend] passthrough: native scraped Bing (no patch)",
              file=sys.stderr, flush=True)
        return

    from autogen_ext.agents.web_surfer import _multimodal_web_surfer as mws
    from autogen_ext.agents.web_surfer.playwright_controller import PlaywrightController

    key = _load_key()
    if not key:
        raise RuntimeError(
            "PERPLEXITY_API_KEY not found (env or repo-root .env) — required for "
            "the perplexity search backend. Set WEBSURFER_SEARCH_BACKEND=bing to "
            "run the original scraped-Bing arm.")

    _tmpdir = tempfile.mkdtemp(prefix="websurfer_serp_")
    _home_url = START_PAGE_OVERRIDE or _write("home.html", _HOME)

    # 1) Never land on bing.com: force the start page (the __init__ default is
    #    bound at class-definition time and _lazy_init goto()s it directly, so
    #    patching DEFAULT_START_PAGE alone is not enough).
    mws.MultimodalWebSurfer.DEFAULT_START_PAGE = _home_url
    _orig_init = mws.MultimodalWebSurfer.__init__

    def __init__(self, *a, **k):
        _orig_init(self, *a, **k)
        if _is_bing(self.start_page or ""):
            self.start_page = _home_url

    mws.MultimodalWebSurfer.__init__ = __init__

    # 2) Intercept the search chokepoint. web_search and the visit_url fallback
    #    both call visit_page(page, "https://www.bing.com/search?q=..."). Turn
    #    that into a real API call rendered as a clean local SERP. Any other
    #    bing.com URL (homepage, etc.) goes to the local home page.
    _orig_visit = PlaywrightController.visit_page

    async def visit_page(self, page, url):
        global _serp_n
        q = _search_query(url)
        if q is not None:
            try:
                import asyncio
                results = await asyncio.get_event_loop().run_in_executor(
                    None, _pplx_search, q, key)
            except Exception as e:
                print(f"[search-backend] search failed for {q!r}: {e!r}",
                      file=sys.stderr, flush=True)
                results = []
            _serp_n += 1
            _log("search", q, len(results))
            url = _write(f"serp_{_serp_n}.html", _render_serp(q, results))
        elif _is_bing(url):
            url = _home_url
        return await _orig_visit(self, page, url)

    PlaywrightController.visit_page = visit_page

    print(f"[search-backend] active: perplexity /search -> clean local SERP "
          f"(max_results={MAX_RESULTS}, home={_home_url})",
          file=sys.stderr, flush=True)


if __name__ == "__main__":
    # Manual check: `python websurfer_debing.py` (in the magentic_v04 env).
    apply()
    print("[search-backend] self-test OK")
