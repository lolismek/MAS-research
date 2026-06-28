"""Run tasks through the CAMEL-style pipeline; score, meter, and persist traces.

A run = (task x tool_profile x arm), arm selecting the AddOn (vanilla today;
belief_board / memory arms later). Each task-run gets a unique proxy tag, so the
whole 4-agent pipeline's calls group under one tag in shared/proxy/calls.jsonl and
we self-meter tokens from there (Tinker exposes no usage API).

Backend is the shared Tinker proxy route (/m/<tag>/v1), model 'gpt-4o' aliased
upstream to Qwen/Qwen3.6-35B-A3B. The proxy must be running (PROXY_URL).

Usage (from repo root). --tasks accepts a benchmark name (benchmarks/<name>/tasks.jsonl),
a path, or a camel-local smoke file (camel/tasks/<name>); --limit N caps the count:
  conda run -n autogen_gc python camel/harness/run_task.py --all                       # default smoke_tasks.json
  conda run -n autogen_gc python camel/harness/run_task.py --tasks gpqa_diamond --limit 2   # smoke 2 GPQA-D
  conda run -n autogen_gc python camel/harness/run_task.py --tasks math_l5 --all        # full MATH level-5
  conda run -n autogen_gc python camel/harness/run_task.py --tasks gaia gaia_50f58759    # one task by id
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
TASKS_DIR = os.path.join(ROOT, "tasks")               # camel-local smoke files
BENCH_DIR = os.path.join(REPO_ROOT, "benchmarks")     # framework-agnostic benchmark data
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

    question = task["question"]
    floc = (task.get("meta") or {}).get("file_local")     # staged attachment (GAIA doc tasks)
    if floc:
        apath = os.path.join(REPO_ROOT, floc)
        question += (f"\n\nAn attached file is available at this exact path:\n{apath}\n"
                     "Call read_file with that path to read its contents.")

    with open(os.path.join(rundir, "prompt.txt"), "w") as f:
        f.write(question)
    with open(os.path.join(rundir, "expected_answer.txt"), "w") as f:
        f.write(str(task["expected_answer"]))

    print(f"[{arm}/{tid}] profile={profile} tools={tool_names} starting", flush=True)
    t0 = time.time()
    res = run_pipeline(question, tool_names, client_for(tag), MODEL, get_addon(arm))
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


def resolve_tasks(spec):
    """Resolve a --tasks spec to a file path. Accepts, in order:
      - a benchmark name   -> benchmarks/<spec>/tasks.jsonl   (e.g. `gpqa_diamond`)
      - a direct path      -> as given, or relative to repo root
      - a camel-local name -> camel/tasks/<spec>             (e.g. `smoke_tasks.json`)
    """
    cands = [os.path.join(BENCH_DIR, spec, "tasks.jsonl"), spec,
             os.path.join(REPO_ROOT, spec), os.path.join(TASKS_DIR, spec)]
    for p in cands:
        if os.path.isfile(p):
            return p
    sys.exit(f"--tasks {spec!r} not found (looked in benchmarks/, cwd, repo root, camel/tasks/)")


def load_tasks(path):
    if path.endswith(".jsonl"):
        return [json.loads(line) for line in open(path) if line.strip()]
    return json.load(open(path))


def pop_opt(args, flag):
    """Pull `--flag value` out of args, returning (value or None, remaining args)."""
    if flag in args:
        i = args.index(flag)
        return args[i + 1], args[:i] + args[i + 2:]
    return None, args


def main():
    args = sys.argv[1:]
    arm, args = pop_opt(args, "--arm"); arm = arm or "vanilla"
    spec, args = pop_opt(args, "--tasks"); spec = spec or "smoke_tasks.json"
    limit, args = pop_opt(args, "--limit")

    tasks = load_tasks(resolve_tasks(spec))
    sel = tasks if (args == ["--all"] or not args) else [t for t in tasks if t["id"] in args]
    if limit:
        sel = sel[:int(limit)]
    if not sel:
        sys.exit(f"no tasks matched {args}; have e.g. {[t['id'] for t in tasks[:8]]}")
    results = [run_one(t, arm=arm) for t in sel]
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
