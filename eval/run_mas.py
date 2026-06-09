"""Run MAF-Magentic on the seed GAIA tasks and capture full transcripts.

Arm: MAF Magentic orchestration (manager + researcher/coder/file specialists) on
MAS_MODEL via Perplexity. Web tooling uses Perplexity Sonar (no browser infra).

Outputs per (task, run): results/runs/<uuid>/<r>/{transcript.txt, events.jsonl,
final_answer.txt, meta.json}. Resume-safe; each run is isolated with a timeout.

!!! TWO THINGS TO VALIDATE LIVE (need the key + `pip install agent-framework`):
  1. CLIENT PATH: does MAF's OpenAIChatClient(base_url=perplexity, model=openai/gpt-5.4-mini)
     actually route to the frontier model? Perplexity serves frontier ids via the
     Responses API; if MAF uses chat.completions it may hit Sonar-only. Run check_api.py
     and a 1-task smoke test FIRST. If it fails, swap to a custom MAF chat client.
  2. USAGE: if MAF doesn't expose per-call token usage, meta cost falls back to a rough
     char/4 estimate (flagged approximate).

Usage:
  python eval/run_mas.py --smoke         # one task, one run (validation)
  python eval/run_mas.py                  # full: all seed tasks x RUNS_PER_TASK
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
from llm_client import call_llm

RUN_TIMEOUT_S = 600


# ---------------------------------------------------------------- tools
# These mirror Magentic-One's agent capabilities as seen in the MAST GAIA traces:
#   WebSurfer        -> web_search (Sonar) + fetch_webpage (navigate + read a page)
#   FileSurfer       -> read_document (PDF / Office / text via markitdown, the same
#                       library Magentic-One's FileSurfer uses)
#   ComputerTerminal -> run_python
# KNOWN GAP vs the original: WebSurfer also *visually* read pages/figures with a
# multimodal model. Perplexity's Responses API rejects image input (verified), so
# we have NO live vision. We compensate with PDF/HTML text extraction, which
# recovers most figure captions / axis labels / society terms that live in text.

_FETCH_MAX_CHARS = 16000          # cap page text to control token cost
_FETCH_TIMEOUT_S = 30
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_MD = None                        # lazily-built MarkItDown converter


def _converter():
    """Build (once) a MarkItDown converter with a browser UA + per-request timeout."""
    global _MD
    if _MD is not None:
        return _MD
    import requests
    from markitdown import MarkItDown
    s = requests.Session()
    s.headers.update({"User-Agent": _UA})
    _orig = s.request
    s.request = lambda *a, **k: _orig(*a, **{**k, "timeout": k.get("timeout", _FETCH_TIMEOUT_S)})
    _MD = MarkItDown(requests_session=s)
    return _MD


def _convert(src: str) -> str:
    """Convert a URL or local path (HTML, PDF, docx, xlsx, ...) to text via markitdown."""
    try:
        r = _converter().convert(src)
        t = (r.text_content or "").strip()
        if not t:
            return "(no extractable text)"
        if len(t) > _FETCH_MAX_CHARS:
            t = t[:_FETCH_MAX_CHARS] + f"\n\n[...truncated at {_FETCH_MAX_CHARS} chars]"
        return t
    except Exception as e:
        return f"(convert error for {src!r}: {type(e).__name__}: {e})"


_SONAR = None


def _sonar_client():
    global _SONAR
    if _SONAR is None:
        from openai import OpenAI
        _SONAR = OpenAI(api_key=C.api_key(), base_url=C.PPLX_BASE_URL)   # chat.completions
    return _SONAR


def web_search(query: str) -> str:
    """Search the web and return a grounded answer PLUS a list of real result links.

    Returns actual source URLs (title, url, date, snippet) so you can then call
    fetch_webpage / read_document on the most relevant ones to read & quote them.

    Args:
        query: A focused natural-language search query.
    """
    try:
        r = _sonar_client().chat.completions.create(
            model="sonar",
            messages=[{"role": "user", "content": query}],
            max_tokens=800, temperature=0)
        d = r.model_dump()
        answer = (r.choices[0].message.content or "").strip()
        results = d.get("search_results") or [
            {"url": u} for u in (d.get("citations") or [])]
        # track sonar cost into the run accumulator
        u = d.get("usage") or {}
        cost = (u.get("cost") or {}).get("total_cost") if isinstance(u.get("cost"), dict) else None
        if cost:
            USAGE_ACC["cost"] += cost
        USAGE_ACC["calls"] += 1
        lines = []
        if answer:
            lines.append(f"Summary: {answer}\n")
        lines.append("Sources (use fetch_webpage/read_document on the relevant URL):")
        for i, s in enumerate(results[:8], 1):
            lines.append(f"[{i}] {s.get('title','(no title)')} — {s.get('url','')}"
                         f"{(' (' + s['date'] + ')') if s.get('date') else ''}\n"
                         f"    {s.get('snippet','')}".rstrip())
        return "\n".join(lines) if (answer or results) else "(no result)"
    except Exception as e:
        return f"(web_search error: {type(e).__name__}: {e})"


def fetch_webpage(url: str) -> str:
    """Open a web page (or arXiv abstract page) and return its readable text.

    Use after web_search to read a specific result, or to navigate directly to a
    known URL. For a PDF/Office document, use read_document instead.

    Args:
        url: Full http(s) URL to fetch.
    """
    return _convert(url)


def read_document(path_or_url: str) -> str:
    """Read a document (PDF, Word, Excel, PowerPoint, CSV, text) and return its text.

    Accepts a local file path or an http(s) URL (e.g. an arXiv PDF link). Use this
    for papers and structured documents where you need the full text/figures-in-text.

    Args:
        path_or_url: Local path or URL to the document.
    """
    return _convert(path_or_url)


def run_python(code: str) -> str:
    """Execute a short Python snippet and return its stdout (for calculations/parsing).

    Args:
        code: Self-contained Python; print the result you need.
    """
    import subprocess
    try:
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=60)
        return (p.stdout or "")[:4000] + (("\n[stderr]\n" + p.stderr[:1000]) if p.returncode else "")
    except Exception as e:
        return f"(run_python error: {e})"


# ---------------------------------------------------------------- MAF wiring
# Real usage accumulator, populated by a tap on every Responses API call (covers
# manager planning + every agent). Perplexity returns true per-call token cost.
USAGE_ACC = {"input": 0, "output": 0, "cost": 0.0, "calls": 0}


def _reset_usage():
    USAGE_ACC.update(input=0, output=0, cost=0.0, calls=0)


def make_client():
    """OpenAIChatClient pointed at Perplexity. Verified live (MAF 1.8.0):
    OpenAIChatClient uses the **Responses API** (client.responses.create), which
    is exactly how Perplexity serves frontier ids like openai/gpt-5.4-mini.
    Base URL MUST include /v1 so the SDK hits /v1/responses (bare host -> 404).
    chat.completions on Perplexity only serves Sonar, so the sibling
    OpenAIChatCompletionClient would NOT work here.

    We tap responses.with_raw_response.create (what MAF calls) to accumulate real
    token usage + Perplexity's exact per-call cost across the whole orchestration."""
    from agent_framework.openai import OpenAIChatClient
    c = OpenAIChatClient(
        model=C.MAS_MODEL,
        api_key=C.api_key(),
        base_url=C.PPLX_BASE_URL + "/v1",
    )
    inner = c.client.responses.with_raw_response.create

    async def _tapped(*a, **k):
        raw = await inner(*a, **k)
        try:
            u = getattr(raw.parse(), "usage", None)   # LegacyAPIResponse caches the parse
            if u is not None:
                USAGE_ACC["input"] += getattr(u, "input_tokens", 0) or 0
                USAGE_ACC["output"] += getattr(u, "output_tokens", 0) or 0
                cost = getattr(u, "cost", None)
                if isinstance(cost, dict):
                    USAGE_ACC["cost"] += cost.get("total_cost", 0.0) or 0.0
                USAGE_ACC["calls"] += 1
        except Exception:
            pass
        return raw

    c.client.responses.with_raw_response.create = _tapped
    return c


# Perplexity's Responses API is STATELESS: it rejects previous_response_id
# chaining. store=False makes MAF resend full history each turn instead of
# relying on server-side response storage. Required for every agent. (verified live)
_NO_STORE = {"store": False}


def build_workflow():
    # Lazy imports so the module parses without agent-framework installed.
    from agent_framework import Agent
    from agent_framework.orchestrations import MagenticBuilder, StandardMagenticManager

    client = make_client()
    researcher = Agent(
        client,
        name="WebSurfer",
        description="Searches the web and reads web pages to find information.",
        instructions=("You find facts on the web. Use web_search to locate sources, then "
                      "fetch_webpage to read a specific page or arXiv abstract in full. "
                      "Quote the concrete evidence (URL + exact text) you found; do not guess "
                      "and do not compute math yourself."),
        tools=[web_search, fetch_webpage], default_options=_NO_STORE)
    coder = Agent(
        client,
        name="ComputerTerminal",
        description="Writes and runs Python for calculations and data parsing.",
        instructions="You solve quantitative subtasks with run_python. Show your work.",
        tools=[run_python], default_options=_NO_STORE)
    filer = Agent(
        client,
        name="FileSurfer",
        description="Reads documents (PDF, Office, text) from a path or URL.",
        instructions=("You read documents with read_document (handles PDFs, Word/Excel/PPT, "
                      "and arXiv PDF links). Extract and quote the relevant details, including "
                      "text inside figures/tables when present."),
        tools=[read_document], default_options=_NO_STORE)
    # The Magentic manager wraps a plain agent and adds the plan + progress-ledger
    # loop. Round/stall/reset caps cap cost & runaway loops.
    manager_agent = Agent(
        client,
        name="MagenticManager",
        description="Coordinates the team to answer the task.",
        instructions=("Coordinate the team to fully answer the task. When the task is solved, "
                      "give the final answer on a line starting exactly with 'FINAL ANSWER:' "
                      "followed by the answer only."),
        default_options=_NO_STORE)
    manager = StandardMagenticManager(
        agent=manager_agent,
        max_round_count=C.MAX_ROUND_COUNT,
        max_stall_count=C.MAX_STALL_COUNT,
        max_reset_count=C.MAX_RESET_COUNT,
    )
    return MagenticBuilder(
        participants=[researcher, coder, filer],
        manager=manager,
        enable_plan_review=False,
        intermediate_output_from="all",     # capture every agent's output for the transcript
    ).build()


def _as_text(obj) -> str:
    """Best-effort text extraction from an output item (AgentResponse/Message/str)."""
    t = getattr(obj, "text", None)
    if t:
        return t if isinstance(t, str) else str(t)
    return str(obj)


def _author(obj) -> str:
    """Recover the speaking agent's name from an AgentResponse."""
    msgs = getattr(obj, "messages", None)
    if msgs:
        for m in reversed(msgs):
            an = getattr(m, "author_name", None)
            if an:
                return an
    return getattr(obj, "agent_id", None) or type(obj).__name__


def _render_ledger(led) -> str:
    """Render a MagenticProgressLedger (the manager's per-round self-assessment +
    the exact instruction it sends the chosen agent) as readable lines."""
    fields = ["is_request_satisfied", "is_in_loop", "is_progress_being_made",
              "next_speaker", "instruction_or_question"]
    out = []
    for f in fields:
        item = getattr(led, f, None)
        if item is None:
            continue
        ans = getattr(item, "answer", "")
        reason = getattr(item, "reason", "")
        out.append(f"  {f}: {ans}" + (f"  — {reason}" if reason else ""))
    return "\n".join(out)


def _render_orchestrator(data):
    """(label, text) for a MagenticOrchestratorEvent: PLAN_CREATED / REPLANNED carry
    the task ledger (a Message); PROGRESS_LEDGER_UPDATED carries the progress ledger."""
    et = getattr(data, "event_type", None)
    et_name = getattr(et, "name", str(et))
    content = getattr(data, "content", None)
    if hasattr(content, "instruction_or_question"):          # progress ledger
        return f"MANAGER · {et_name} (progress ledger)", _render_ledger(content)
    return f"MANAGER · {et_name} (task ledger)", _as_text(content)   # Message


async def run_one(workflow, task_prompt: str):
    """Run the workflow and capture the FULL event stream in order.

    Earlier this used only get_intermediate_outputs()+get_outputs(), which keep ONLY
    the specialist replies and final answer and SILENTLY DROP every
    `magentic_orchestrator` event — the manager's plan, re-plans, and per-round
    progress ledgers (incl. the exact instruction sent to each agent). Those are the
    most important evidence for coordination/verification failure modes, so we now
    iterate the whole result (WorkflowRunResult is the complete event list).
    """
    result = await workflow.run(task_prompt)        # -> WorkflowRunResult (list-like)

    lines, events = [], []
    final_answer = None
    for ev in result:                               # full event stream, in order
        etype = getattr(ev, "type", None)
        data = getattr(ev, "data", None)
        if etype == "magentic_orchestrator":
            label, text = _render_orchestrator(data)
            lines.append(f"\n========== {label} ==========\n{text}")
            events.append({"kind": etype, "author": "MagenticManager",
                           "type": getattr(getattr(data, "event_type", None), "name", ""),
                           "text": text[:4000]})
        elif etype == "intermediate":
            lines.append(f"\n---------- {_author(data)} ----------\n{_as_text(data)}")
            events.append({"kind": etype, "author": _author(data),
                           "type": type(data).__name__, "text": _as_text(data)[:4000]})
        elif etype == "output":
            final_answer = _as_text(data)
            lines.append(f"\n---------- FINAL OUTPUT ----------\n{final_answer}")
            events.append({"kind": etype, "author": _author(data),
                           "type": type(data).__name__, "text": _as_text(data)[:4000]})
    transcript = "".join(lines) if lines else "(empty transcript)"

    # usage: real token counts + Perplexity's exact cost from the client tap.
    if USAGE_ACC["calls"] > 0:
        pin, pout = C.PRICES.get(C.MAS_MODEL, (0, 0))
        price_cost = USAGE_ACC["input"] / 1e6 * pin + USAGE_ACC["output"] / 1e6 * pout
        usage = {"input_tokens": USAGE_ACC["input"], "output_tokens": USAGE_ACC["output"],
                 "n_llm_calls": USAGE_ACC["calls"],
                 "cost_usd": USAGE_ACC["cost"] or price_cost,
                 "cost_source": "perplexity" if USAGE_ACC["cost"] else "price_table",
                 "approximate": not bool(USAGE_ACC["cost"])}
    else:  # fallback: char/4 estimate
        approx_tok = max(1, len(transcript) // 4)
        pin, pout = C.PRICES.get(C.MAS_MODEL, (0, 0))
        usage = {"input_tokens": approx_tok, "output_tokens": approx_tok // 4,
                 "cost_usd": approx_tok / 1e6 * pin + (approx_tok // 4) / 1e6 * pout,
                 "approximate": True, "cost_source": "char_estimate"}
    return transcript, events, final_answer, usage


def _attachment_path(task):
    """Return the local GAIA attachment for a task (<uuid>.<ext> in its trace dir), or None.

    The original Magentic-One was given these files; including them keeps the
    comparison faithful. read_document (markitdown) reads PDF/Office/text — but NOT
    audio (no transcription in our stack), so .mp3/.wav tasks stay blocked."""
    d = C.GAIA_LEVEL_DIRS.get(task["level"], None)
    if not d:
        return None
    hits = list((d / task["uuid"] / "0").glob(task["uuid"] + ".*"))
    return hits[0] if hits else None


def task_prompt(task) -> str:
    """Task prompt, augmented with the local attachment path when one exists."""
    p = task["prompt"]
    att = _attachment_path(task)
    if att:
        p += (f"\n\n[A file is attached for this task at the local path: {att}\n"
               f"Use read_document on that exact path to read it.]")
    return p


def do_run(task, run_idx):
    out_dir = C.RUNS_DIR / task["uuid"] / str(run_idx)
    if (out_dir / "transcript.txt").exists():
        print("skip (exists):", out_dir); return
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        _reset_usage()
        # A MAF workflow instance is SINGLE-USE (errors on a 2nd run), so build a
        # fresh one for every run.
        workflow = build_workflow()
        transcript, events, final, usage = asyncio.run(
            asyncio.wait_for(run_one(workflow, task_prompt(task)), RUN_TIMEOUT_S))
        meta = {"rounds": None, "error": None, "usage": usage,
                "wall_clock_s": round(time.time() - t0, 1)}
        (out_dir / "transcript.txt").write_text(transcript)
        (out_dir / "final_answer.txt").write_text(final or "")
        with open(out_dir / "events.jsonl", "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
    except Exception as e:
        meta = {"error": repr(e), "usage": None, "wall_clock_s": round(time.time() - t0, 1)}
        (out_dir / "transcript.txt").write_text(f"(run failed: {e!r})")
        (out_dir / "final_answer.txt").write_text("")
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"ran {task['uuid']} run {run_idx} ({meta['wall_clock_s']}s) err={meta.get('error')}")


def main(smoke=False, level=None):
    tasks = [json.loads(l) for l in open(C.TASKS_JSONL)]
    if smoke:
        pool = [t for t in tasks if level is None or t.get("level") == level]
        if not pool:
            print(f"no task at level {level}; falling back to first task"); pool = tasks
        t = pool[0]
        print(f"smoke: task {t['uuid']} (level {t.get('level')})")
        do_run(t, 0); return
    for t in tasks:
        for r in range(C.RUNS_PER_TASK):
            do_run(t, r)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--level", type=int, default=None, help="restrict --smoke to this GAIA level")
    a = ap.parse_args()
    main(smoke=a.smoke, level=a.level)
