"""De-Bing the Magentic-One WebSurfer (Layer A intervention).

Why this exists
---------------
autogen_ext 0.4.8 ``MultimodalWebSurfer`` hardwires Bing in three places:
  * ``DEFAULT_START_PAGE`` = https://www.bing.com/
  * the only ``web_search`` tool issues https://www.bing.com/search?q=...
  * ``visit_url`` silently rewrites any non-URL arg (a query containing a space)
    into the same Bing search URL.
So when the Orchestrator tells WebSurfer "avoid Bing, navigate directly", the
agent *cannot* comply — there is no non-Bing affordance in its action space.
Bing's CAPTCHA wall then deadlocks the run regardless of instructions. In the
gpt-5.4-mini reproduction this was the dominant Magentic-One failure signature
and it is a harness artifact, not inter-agent misalignment.

What it does
------------
Monkeypatches the *installed* package at runtime (no site-packages edit) to
route every Bing search through a CAPTCHA-free SERP. Both search call sites
funnel through ``PlaywrightController.visit_page(page, url)`` — the single
chokepoint we wrap — so rewriting Bing URLs there catches both ``web_search``
and the ``visit_url`` fallback. ``DEFAULT_START_PAGE`` is patched too.

Loaded automatically by the sibling ``sitecustomize.py`` when
``reproduction/magentic/_debing`` is on ``PYTHONPATH`` — ``run_task.py`` puts it
there for the scenario.py subprocess, so the conda env stays vanilla.

Knobs (env), defaults are the de-Bing'd arm
-------------------------------------------
  WEBSURFER_SEARCH_URL   default  https://html.duckduckgo.com/html/?q={q}
  WEBSURFER_START_PAGE   default  https://duckduckgo.com/
Reproduce the original Bing arm by exporting:
  WEBSURFER_SEARCH_URL='https://www.bing.com/search?q={q}&FORM=QBLH'
  WEBSURFER_START_PAGE='https://www.bing.com/'
Use ``{q}`` as the URL-encoded-query placeholder in WEBSURFER_SEARCH_URL.
"""
import os
import sys
from urllib.parse import parse_qs, quote_plus, urlparse

SEARCH_URL = os.environ.get("WEBSURFER_SEARCH_URL", "https://html.duckduckgo.com/html/?q={q}")
START_PAGE = os.environ.get("WEBSURFER_START_PAGE", "https://duckduckgo.com/")

_applied = False


def apply():
    """Idempotently install the monkeypatch. Raises on failure (fail loud:
    a broken patch must abort the run, never silently fall back to Bing)."""
    global _applied
    if _applied:
        return

    from autogen_ext.agents.web_surfer import _multimodal_web_surfer as mws
    from autogen_ext.agents.web_surfer.playwright_controller import PlaywrightController

    # 1) start page (class default, used unless scenario.py passes start_page).
    mws.MultimodalWebSurfer.DEFAULT_START_PAGE = START_PAGE

    # 2) reroute every Bing search the agent emits, at the shared chokepoint.
    _orig_visit = PlaywrightController.visit_page

    async def visit_page(self, page, url):
        if "bing.com/search" in url:
            # q is already percent-decoded by parse_qs; re-encode into the SERP.
            q = parse_qs(urlparse(url).query).get("q", [""])[0]
            url = SEARCH_URL.format(q=quote_plus(q))
        return await _orig_visit(self, page, url)

    PlaywrightController.visit_page = visit_page
    _applied = True
    print(f"[de-bing] active: search={SEARCH_URL!r} start={START_PAGE!r}",
          file=sys.stderr, flush=True)


if __name__ == "__main__":
    # Manual check: `python websurfer_debing.py` (in the magentic_v04 env).
    apply()
    print("[de-bing] self-test OK")
