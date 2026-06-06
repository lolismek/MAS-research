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
def web_search(query: str) -> str:
    """Search the web for up-to-date information and return a grounded summary.

    Args:
        query: A focused natural-language search query.
    """
    try:
        text, _ = call_llm(query, "perplexity/sonar", temperature=0, max_output_tokens=1200)
        return text or "(no result)"
    except Exception as e:
        return f"(web_search error: {e})"


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
def build_workflow():
    # Lazy imports so the module parses without agent-framework installed.
    from agent_framework import Agent
    from agent_framework.openai import OpenAIChatClient        # TODO confirm import/params
    from agent_framework.orchestrations import MagenticBuilder

    client = OpenAIChatClient(
        api_key=C.api_key(),
        base_url=C.PPLX_BASE_URL + "/v1",
        model_id=C.MAS_MODEL,
    )
    researcher = Agent(
        name="ResearcherAgent",
        description="Finds information from the web.",
        instructions="You research facts using web_search. Report findings; do not compute.",
        client=client, tools=[web_search])
    coder = Agent(
        name="CoderAgent",
        description="Writes and runs Python for calculations and data parsing.",
        instructions="You solve quantitative subtasks with run_python. Show your work.",
        client=client, tools=[run_python])
    filer = Agent(
        name="FileAgent",
        description="Reads and reasons over provided text.",
        instructions="You extract and summarize relevant details from provided content.",
        client=client)
    manager = Agent(
        name="MagenticManager",
        description="Coordinates the team to answer the task.",
        instructions=("Coordinate the team to fully answer the task, then give a final answer "
                      "on a line starting exactly with 'FINAL ANSWER:' followed by the answer only."),
        client=client)
    return MagenticBuilder(
        participants=[researcher, coder, filer],
        manager_agent=manager,
        enable_plan_review=False,
        max_round_count=C.MAX_ROUND_COUNT,
        max_stall_count=C.MAX_STALL_COUNT,
        max_reset_count=C.MAX_RESET_COUNT,
    ).build()


async def run_one(workflow, task_prompt: str):
    """Run the workflow; return (transcript_text, events, final_answer, usage)."""
    from agent_framework import AgentResponse, AgentResponseUpdate

    events, buf, order = [], {}, []          # buf: msg_id -> [executor, text]
    final_answer = None

    async for event in workflow.run(task_prompt, stream=True):
        try:
            events.append({"type": getattr(event, "type", None),
                           "executor": getattr(event, "executor_id", None),
                           "data": str(getattr(event, "data", ""))[:2000]})
        except Exception:
            pass
        et = getattr(event, "type", None)
        data = getattr(event, "data", None)
        if et == "output" and isinstance(data, AgentResponseUpdate):
            mid = getattr(data, "message_id", None) or id(data)
            if mid not in buf:
                buf[mid] = [getattr(event, "executor_id", "?"), ""]
                order.append(mid)
            buf[mid][1] += str(data)
        elif et == "magentic_orchestrator":
            order.append(("orch", str(getattr(data, "event_type", "")), str(getattr(data, "content", ""))[:3000]))
        elif et == "output" and isinstance(data, AgentResponse):
            final_answer = data.messages[-1].text if getattr(data, "messages", None) else None

    # flatten transcript
    lines = []
    for o in order:
        if isinstance(o, tuple) and o[0] == "orch":
            lines.append(f"\n---------- ORCHESTRATOR [{o[1]}] ----------\n{o[2]}")
        elif o in buf:
            who, txt = buf[o]
            lines.append(f"\n---------- {who} ----------\n{txt}")
    if final_answer:
        lines.append(f"\nFINAL ANSWER: {final_answer}")
    transcript = "".join(lines)

    # usage: MAF may not expose it -> rough estimate (flagged)
    approx_tok = max(1, len(transcript) // 4)
    pin, pout = C.PRICES.get(C.MAS_MODEL, (0, 0))
    usage = {"input_tokens": approx_tok, "output_tokens": approx_tok // 4,
             "cost_usd": approx_tok / 1e6 * pin + (approx_tok // 4) / 1e6 * pout,
             "approximate": True}
    return transcript, events, final_answer, usage


def do_run(workflow, task, run_idx):
    out_dir = C.RUNS_DIR / task["uuid"] / str(run_idx)
    if (out_dir / "transcript.txt").exists():
        print("skip (exists):", out_dir); return
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        transcript, events, final, usage = asyncio.run(
            asyncio.wait_for(run_one(workflow, task["prompt"]), RUN_TIMEOUT_S))
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


def main(smoke=False):
    tasks = [json.loads(l) for l in open(C.TASKS_JSONL)]
    workflow = build_workflow()
    if smoke:
        do_run(workflow, tasks[0], 0); return
    for t in tasks:
        for r in range(C.RUNS_PER_TASK):
            do_run(workflow, t, r)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    main(smoke=ap.parse_args().smoke)
