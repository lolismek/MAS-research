"""Cell runner: (task x N x arm) -> scored, metered, persisted trace.

A run = one task through the chainloss relay at chain length N under one channel
arm. Backend is the shared Tinker proxy route (/m/<tag>/v1), model 'gpt-4o' aliased
upstream to Qwen/Qwen3.6-35B-A3B; the proxy must be running (PROXY_URL). Unlike
duet, token/cost metering comes straight from response `usage` (the per-shift
TokenMeter ledgers) — no proxy-log dependency.

Traces land in chainloss/traces/<arm>/n<N>/<bench>/<id>/run_K/.

Usage (from the repo root; --tasks accepts a chainloss/tasks/ name or a path):
  conda run -n autogen_gc python chainloss/harness/run_task.py --tasks fanoutqa.jsonl --n 1 --all
  conda run -n autogen_gc python chainloss/harness/run_task.py --tasks fanoutqa.jsonl --n 8 --arm transcript fanout_003

Knobs: --n = chain length; --arm = note|transcript; --budget = TOTAL completion
tokens for the run (default relay.DEFAULT_TOTAL_BUDGET, split evenly across shifts).
"""
import json, os, re, sys, time

from openai import OpenAI

from relay import run_relay, DEFAULT_TOTAL_BUDGET, ARMS
from agent import Budget
from tools import TOOL_PROFILES
from scoring import classify_outcome, list_recall
import prompts

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # chainloss/
TASKS_DIR = os.path.join(ROOT, "tasks")
TRACES = os.path.join(ROOT, "traces")

PROXY = os.environ.get("PROXY_URL", "http://127.0.0.1:8744/v1")
MODEL = os.environ.get("CHAINLOSS_MODEL", "gpt-4o")   # aliased to Qwen by the proxy

# Tinker console rates for Qwen/Qwen3.6-35B-A3B, USD per MILLION tokens.
PREFILL_PER_MTOK = float(os.environ.get("CHAINLOSS_PREFILL_RATE", 0.36))
SAMPLE_PER_MTOK = float(os.environ.get("CHAINLOSS_SAMPLE_RATE", 0.89))

# Per-task USD safety cap: a runaway task stops and publishes an honest UNKNOWN.
BUDGET_USD = float(os.environ.get("CHAINLOSS_BUDGET_USD", "2.0"))


def parse_final(text):
    m = re.findall(r"FINAL ANSWER:\s*(.+)", text or "")
    return m[-1].strip() if m else (text or "").strip()


def client_for(tag):
    base, v1 = PROXY.rsplit("/", 1)
    return OpenAI(base_url=f"{base}/m/{tag}/{v1}", api_key="dummy")


def run_one(task, n, arm="note", total_budget=None, budget_usd=None):
    total_budget = total_budget if total_budget is not None else DEFAULT_TOTAL_BUDGET
    tid = task["id"]
    bench = task.get("bench", "unknown")
    profile = task.get("tool_profile", "none")
    tool_names = TOOL_PROFILES[profile]

    runs_dir = os.path.join(TRACES, arm, f"n{n}", bench, tid)
    k = 1
    while os.path.exists(os.path.join(runs_dir, f"run_{k}")):
        k += 1
    rundir = os.path.join(runs_dir, f"run_{k}")
    os.makedirs(rundir)
    tag = f"chainloss_{arm}_n{n}_{tid}_run{k}"

    question = task["question"]
    with open(os.path.join(rundir, "prompt.txt"), "w") as f:
        f.write(question)
    with open(os.path.join(rundir, "expected_answer.txt"), "w") as f:
        f.write(str(task["expected_answer"]))

    print(f"[{arm}/n{n}/{tid}] profile={profile} budget={total_budget} starting", flush=True)
    t0 = time.time()
    usd = Budget(BUDGET_USD if budget_usd is None else budget_usd,
                 PREFILL_PER_MTOK, SAMPLE_PER_MTOK)
    client = client_for(tag)
    res = run_relay(question, tool_names, client, MODEL, n=n, arm=arm,
                    total_budget=total_budget, usd_budget=usd)
    dur = time.time() - t0

    # Edge yield: what actually crossed each edge. A marker means the producer left
    # no usable payload, so ZERO information transferred there — a first-class axis
    # (a rising marker rate with N is itself channel loss).
    edges = len(res.payloads)
    markers = sum(1 for p in res.payloads if p == prompts.TRUNCATED_MARKER)
    note_yield = round((edges - markers) / edges, 3) if edges else None

    final = parse_final(res.final)
    expected = str(task["expected_answer"])
    answer_type = task.get("answer_type", "freeform")
    outcome = classify_outcome(final, expected, answer_type, committed=res.committed)
    recall = list_recall(final, expected, answer_type)

    pt = sum(s["prompt"] for s in res.per_shift)
    ct = sum(s["completion"] for s in res.per_shift)
    cost = round(pt / 1e6 * PREFILL_PER_MTOK + ct / 1e6 * SAMPLE_PER_MTOK, 6)

    result = dict(
        id=tid, bench=bench, arm=arm, n=n, run=k, tool_profile=profile,
        answer_type=answer_type, seconds=round(dur, 1),
        total_budget=total_budget, slice_budget=res.slice_budget,
        final_answer=final, expected_answer=expected,
        outcome=outcome, recall=recall, exact_match=outcome == "correct",
        committed=res.committed, budget_exceeded=res.budget_exceeded, finish=res.finish,
        edges=edges, edge_markers=markers, note_yield=note_yield,
        shifts_used=res.shifts_used, n_calls=res.n_calls, n_tool_calls=res.n_tool_calls,
        completion_tokens=ct, prompt_tokens=pt, total_tokens=pt + ct, cost_usd=cost,
        tokens_overrun=sum(s["overrun"] for s in res.per_shift),
        per_shift=res.per_shift,
        per_agent=[dict(role=a.role, finish=a.finish, steps=a.n_steps,
                        tool_calls=a.n_tool_calls, final=(a.final or "")[:400])
                   for a in res.agents])

    with open(os.path.join(rundir, "result.json"), "w") as f:
        json.dump(result, f, indent=1)
    with open(os.path.join(rundir, "transcript.json"), "w") as f:
        json.dump([dict(role=a.role, finish=a.finish, transcript=a.transcript)
                   for a in res.agents], f, indent=1)
    if res.payloads:                               # what crossed each edge
        fname = "handoff_notes.txt" if arm == "note" else "work_logs.txt"
        with open(os.path.join(rundir, fname), "w") as f:
            for j, p in enumerate(res.payloads, 1):
                f.write(f"===== edge {j} =====\n{p}\n\n")

    print(f"[{arm}/n{n}/{tid}] {dur:.0f}s final={final!r} expected={expected!r} "
          f"outcome={outcome} recall={recall if recall is None else round(recall, 2)}"
          f"{' [USD-CAP]' if res.budget_exceeded else ''} "
          f"ctok={ct}/{total_budget} (overrun {result['tokens_overrun']}) "
          f"calls={res.n_calls} tools={res.n_tool_calls} notes={edges - markers}/{edges} "
          f"cost=${cost:.3f} finishes={[a.finish for a in res.agents]}", flush=True)
    return result


def resolve_tasks(spec):
    cands = [spec, os.path.join(TASKS_DIR, spec), os.path.join(ROOT, spec)]
    for p in cands:
        if os.path.isfile(p):
            return p
    sys.exit(f"--tasks {spec!r} not found (looked in cwd, chainloss/tasks/, chainloss/)")


def load_tasks(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def pop_opt(args, flag):
    if flag in args:
        i = args.index(flag)
        return args[i + 1], args[:i] + args[i + 2:]
    return None, args


def main():
    args = sys.argv[1:]
    spec, args = pop_opt(args, "--tasks"); spec = spec or "fanoutqa.jsonl"
    n, args = pop_opt(args, "--n"); n = int(n) if n else 1
    arm, args = pop_opt(args, "--arm"); arm = arm or "note"
    budget, args = pop_opt(args, "--budget"); budget = int(budget) if budget else None
    limit, args = pop_opt(args, "--limit")

    if arm not in ARMS:
        sys.exit(f"unknown arm {arm!r}; have {ARMS}")
    tasks = load_tasks(resolve_tasks(spec))
    sel = tasks if (args == ["--all"] or not args) else [t for t in tasks if t["id"] in args]
    if limit:
        sel = sel[:int(limit)]
    if not sel:
        sys.exit(f"no tasks matched {args}; have e.g. {[t['id'] for t in tasks[:8]]}")
    results = [run_one(t, n=n, arm=arm, total_budget=budget) for t in sel]
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
