"""Run tasks through the CAMEL-style pipeline; score, meter, and persist traces.

A run = (task x tool_profile x arm), arm selecting the AddOn (vanilla today;
belief_board / memory arms later). Each task-run gets a unique proxy tag, so the
whole 4-agent pipeline's calls group under one tag in shared/proxy/calls.jsonl and
we self-meter tokens from there (Tinker exposes no usage API).

Backend is the shared Tinker proxy route (/m/<tag>/v1), model 'gpt-4o' aliased
upstream to Qwen/Qwen3.6-35B-A3B. The proxy must be running (PROXY_URL).

Usage (from repo root):
  conda run -n autogen_gc python camel/harness/run_task.py --all
  conda run -n autogen_gc python camel/harness/run_task.py smoke_math
  conda run -n autogen_gc python camel/harness/run_task.py --arm vanilla --tasks smoke_tasks.json --all
"""
import json, os, re, sys, time

from openai import OpenAI

from pipeline import run_pipeline
from tools import TOOL_PROFILES
from addons import get_addon
from scoring import classify_outcome

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # camel/
REPO_ROOT = os.path.dirname(ROOT)                  # multi-benchmark-eval/
TASKS_DIR = os.path.join(ROOT, "tasks")
TRACES = os.path.join(ROOT, "traces")
CALLS_LOG = os.path.join(REPO_ROOT, "shared", "proxy", "calls.jsonl")

PROXY = os.environ.get("PROXY_URL", "http://127.0.0.1:8744/v1")
MODEL = os.environ.get("CAMEL_MODEL", "gpt-4o")    # aliased to Qwen by the proxy

# Tinker console rates for Qwen/Qwen3.6-35B-A3B, USD per MILLION tokens (2026-06-27).
# No Tinker usage API → we self-meter tokens from calls.jsonl and price them here.
PREFILL_PER_MTOK = float(os.environ.get("CAMEL_PREFILL_RATE", 0.36))
SAMPLE_PER_MTOK = float(os.environ.get("CAMEL_SAMPLE_RATE", 0.89))


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[,$%]", "", (s or "").strip().lower()))


def parse_final(text):
    m = re.findall(r"FINAL ANSWER:\s*(.+)", text or "")
    return m[-1].strip() if m else (text or "").strip()


def client_for(tag):
    base, v1 = PROXY.rsplit("/", 1)                # http://127.0.0.1:8744 , v1
    return OpenAI(base_url=f"{base}/m/{tag}/{v1}", api_key="dummy")


def meter(tag, t0):
    """Sum tokens/calls for this run's tag from the proxy log (lines after t0)."""
    pt = ct = n = errs = 0
    if os.path.exists(CALLS_LOG):
        for line in open(CALLS_LOG):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("tag") != tag or r.get("ts", 0) < t0 - 1:
                continue
            n += 1
            if r.get("error"):
                errs += 1
                continue
            pt += r.get("prompt_tokens", 0) or 0
            ct += r.get("completion_tokens", 0) or 0
    cost = round(pt / 1e6 * PREFILL_PER_MTOK + ct / 1e6 * SAMPLE_PER_MTOK, 6)
    return dict(proxy_calls=n, proxy_errors=errs,
                prompt_tokens=pt, completion_tokens=ct, total_tokens=pt + ct,
                cost_usd=cost)


def run_one(task, arm="vanilla"):
    tid = task["id"]
    profile = task.get("tool_profile", "none")
    tool_names = TOOL_PROFILES[profile]
    runs_dir = os.path.join(TRACES, arm, tid)
    n = 1
    while os.path.exists(os.path.join(runs_dir, f"run_{n}")):
        n += 1
    rundir = os.path.join(runs_dir, f"run_{n}")
    os.makedirs(rundir)
    tag = f"camel_{arm}_{tid}_run{n}"

    with open(os.path.join(rundir, "prompt.txt"), "w") as f:
        f.write(task["question"])
    with open(os.path.join(rundir, "expected_answer.txt"), "w") as f:
        f.write(str(task["expected_answer"]))

    print(f"[{arm}/{tid}] profile={profile} tools={tool_names} starting", flush=True)
    t0 = time.time()
    res = run_pipeline(task["question"], tool_names, client_for(tag), MODEL, get_addon(arm))
    dur = time.time() - t0

    final = parse_final(res.final)
    expected = str(task["expected_answer"])
    answer_type = task.get("answer_type", "freeform")
    outcome = classify_outcome(final, expected, answer_type)   # correct/abstained/wrong_confident
    result = dict(
        id=tid, arm=arm, run=n, bench=task.get("bench"), tool_profile=profile,
        answer_type=answer_type, seconds=round(dur, 1),
        final_answer=final, expected_answer=expected,
        outcome=outcome,
        exact_match=outcome == "correct",        # kept for the viewer's pass/fail
        n_calls=res.n_calls, n_tool_calls=res.n_tool_calls,
        per_agent=[dict(role=a.role, steps=a.n_steps, tool_calls=a.n_tool_calls,
                        final=a.final[:300]) for a in res.agents],
        **meter(tag, t0))
    with open(os.path.join(rundir, "result.json"), "w") as f:
        json.dump(result, f, indent=1)
    with open(os.path.join(rundir, "transcript.json"), "w") as f:
        json.dump([dict(role=a.role, transcript=a.transcript) for a in res.agents], f, indent=1)

    print(f"[{arm}/{tid}] {dur:.0f}s final={final!r} expected={expected!r} "
          f"outcome={outcome} calls={res.n_calls} tools={res.n_tool_calls} "
          f"tok={result['total_tokens']} per_agent="
          f"{[(a.role, a.n_steps, a.n_tool_calls) for a in res.agents]}", flush=True)
    return result


def main():
    args = sys.argv[1:]
    arm = "vanilla"
    if "--arm" in args:
        i = args.index("--arm"); arm = args[i + 1]; args = args[:i] + args[i + 2:]
    tasks_file = "smoke_tasks.json"
    if "--tasks" in args:
        i = args.index("--tasks"); tasks_file = args[i + 1]; args = args[:i] + args[i + 2:]
    tasks = json.load(open(os.path.join(TASKS_DIR, tasks_file)))
    sel = tasks if args == ["--all"] or not args else [t for t in tasks if t["id"] in args]
    if not sel:
        sys.exit(f"no tasks matched {args}; have {[t['id'] for t in tasks]}")
    results = [run_one(t, arm=arm) for t in sel]
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
