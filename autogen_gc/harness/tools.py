"""Function tools for the AutoGen SelectorGroupChat MAS.

Web access here is a pair of plain function tools — NOT the browser
``MultimodalWebSurfer``. This is deliberate: in this system each agent is an
``AssistantAgent(max_tool_iterations=K)`` that runs a deep *internal* tool loop
(model -> tool -> model -> ...) entirely inside its private ``inner_messages``,
then publishes ONE message to the group chat. ``max_tool_iterations`` loops on
*tools*, so web access must be a tool, not a separate agent. Using tools also
drops the Playwright/Bing/CAPTCHA surface entirely (the original robustness goal);
the only thing lost vs. the browser is page *vision* (web is text-only here),
which the task-set doability filter accounts for.

``web_search`` reuses the exact Perplexity ``/search`` call from the Magentic
de-Bing backend (``reproduction/magentic/_debing/websurfer_debing.py``) — lifted
verbatim so both systems hit the same search API. ``run_python`` executes code in
a subprocess (same local-trust model as Magentic-One's LocalCommandLineCodeExecutor).

All three functions are plain, annotated callables with docstrings: AutoGen wraps
each as a FunctionTool and uses the docstring as the tool description, so the
wording below is what the model sees.
"""
import os
import subprocess
import sys

import requests

PPLX_SEARCH_URL = os.environ.get("PPLX_SEARCH_URL", "https://api.perplexity.ai/search")
MAX_RESULTS = int(os.environ.get("WEBSURFER_MAX_RESULTS", "10"))
FETCH_MAX_CHARS = int(os.environ.get("FETCH_MAX_CHARS", "8000"))
PYTHON_TIMEOUT = int(os.environ.get("RUN_PYTHON_TIMEOUT", "30"))

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

_key = None


def _load_key():
    """PERPLEXITY_API_KEY from env, else from the nearest ancestor .env.

    Lifted from reproduction/magentic/_debing/websurfer_debing.py so the two
    systems share one key-resolution path.
    """
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


def _pplx_search(query, key):
    """The Perplexity /search call, lifted verbatim from the de-Bing backend."""
    r = requests.post(
        PPLX_SEARCH_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"query": query, "max_results": MAX_RESULTS},
        timeout=60,
    )
    r.raise_for_status()
    return r.json().get("results", [])


def web_search(query: str) -> str:
    """Search the web and return a numbered list of results (title, URL, snippet).

    Use this to find pages relevant to the task. The snippet is only a preview —
    to read a page's full content, pass its URL to ``fetch_url``.
    """
    global _key
    if _key is None:
        _key = _load_key()
    if not _key:
        return "ERROR: PERPLEXITY_API_KEY not configured; web_search is unavailable."
    try:
        results = _pplx_search(query, _key)
    except Exception as e:  # surface the error to the model, don't crash the turn
        return f"ERROR: web_search failed for {query!r}: {e!r}"
    if not results:
        return f'No results for "{query}".'
    lines = [f'Search results for "{query}":', ""]
    for i, x in enumerate(results, 1):
        title = (x.get("title") or x.get("url") or "(untitled)").strip()
        url = (x.get("url") or "").strip()
        snippet = " ".join((x.get("snippet") or "").split())
        lines.append(f"[{i}] {title}")
        lines.append(f"    {url}")
        if snippet:
            lines.append(f"    {snippet}")
        lines.append("")
    return "\n".join(lines).rstrip()


def fetch_url(url: str) -> str:
    """Fetch a web page and return its readable text content (truncated).

    Use this after ``web_search`` to read the full text of a promising result.
    Returns plain text with scripts/styles removed; long pages are truncated.
    """
    try:
        from bs4 import BeautifulSoup
    except Exception as e:
        return f"ERROR: bs4 not available: {e!r}"
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=45)
        r.raise_for_status()
    except Exception as e:
        return f"ERROR: fetch_url failed for {url!r}: {e!r}"
    ctype = r.headers.get("Content-Type", "")
    if "html" not in ctype and "xml" not in ctype and ctype:
        # plain text / json / etc — return as-is, truncated
        text = r.text
    else:
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        text = soup.get_text("\n")
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if len(text) > FETCH_MAX_CHARS:
        text = text[:FETCH_MAX_CHARS] + f"\n\n[...truncated at {FETCH_MAX_CHARS} chars...]"
    return text or f"(no extractable text at {url})"


def run_python(code: str) -> str:
    """Execute a Python 3 snippet and return its stdout (and stderr on error).

    Use this for reliable computation — arithmetic, counting, parsing, dates, etc.
    The code runs in a fresh subprocess; print() what you want to see. No state is
    kept between calls, so each call must be self-contained.
    """
    try:
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=PYTHON_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"ERROR: code timed out after {PYTHON_TIMEOUT}s."
    out = p.stdout or ""
    if p.returncode != 0:
        return (out + ("\n" if out else "") + "STDERR:\n" + (p.stderr or "")).strip() \
            or f"(exited {p.returncode} with no output)"
    return out.strip() or "(ran successfully, no stdout)"


if __name__ == "__main__":
    # Manual smoke: python tools.py
    print(run_python("print(1037 * 0.04)"))
    print("---")
    print(web_search("Rockhopper penguin")[:400])
