"""Aggregate the per-task result.json files into per-(arm, benchmark) stats.

Single source of truth shared by `make_results.py` (writes RESULTS.md) and the
viewer's summary dashboard, so the two never drift. Two cleanups vs. a raw scan:
  - DEDUP to the latest run per (arm, task) — retries don't get double-counted.
  - RESTRICT to the official evaluated id set (benchmarks/<b>/tasks.jsonl) when that
    file is present — stale smoke runs / dropped ids don't leak into the headline.
The 3-way outcome is the honesty axis: correct / abstained(honest UNKNOWN) /
wrong_confident(hallucinated).
"""
import json, os, re, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # camel/
REPO_ROOT = os.path.dirname(ROOT)
TRACES = os.path.join(ROOT, "traces")
BENCH_DIR = os.path.join(REPO_ROOT, "benchmarks")

# benchmark dir -> display title, in report order
BENCHES = [("gpqa_diamond", "GPQA-Diamond"), ("math_l5", "MATH-L5"), ("gaia", "GAIA"),
           ("popqa", "PopQA"), ("fever", "FEVER"), ("pddl", "PDDL")]
TITLE = dict(BENCHES)


def eval_ids():
    """{bench: set(task_id)} from benchmarks/<b>/tasks.jsonl, when present."""
    out = {}
    for b, _ in BENCHES:
        p = os.path.join(BENCH_DIR, b, "tasks.jsonl")
        if os.path.exists(p):
            out[b] = {json.loads(l)["id"] for l in open(p) if l.strip()}
    return out


def _bench_of(tid, ids):
    """Which benchmark a task id belongs to — by membership if we have the id sets,
    else by id prefix as a fallback."""
    for b, _ in BENCHES:
        if b in ids and tid in ids[b]:
            return b
    for pre, b in (("gpqad", "gpqa_diamond"), ("math_l5", "math_l5"), ("gaia_", "gaia"),
                   ("popqa_", "popqa"), ("fever_", "fever"), ("pddl_", "pddl")):
        if tid.startswith(pre):
            return b
    return None


def latest_runs(arm):
    """Latest run per task for one arm: {tid: result_dict}."""
    out = {}
    for f in glob.glob(os.path.join(TRACES, arm, "*", "run_*", "result.json")):
        tid = os.path.basename(os.path.dirname(os.path.dirname(f)))
        m = re.search(r"run_(\d+)", f)
        rn = int(m.group(1)) if m else 0
        if tid not in out or rn > out[tid][0]:
            try:
                out[tid] = (rn, json.load(open(f)))
            except Exception:
                continue
    return {tid: r for tid, (rn, r) in out.items()}


def arms():
    if not os.path.isdir(TRACES):
        return []
    return sorted(d for d in os.listdir(TRACES) if os.path.isdir(os.path.join(TRACES, d)))


def summarize(arm, restrict=True):
    """Per-benchmark stats for one arm. restrict=True keeps only official evaluated ids.
    Returns {bench: dict(n, correct, abstained, wrong_confident, cost, seconds, tools)}."""
    ids = eval_ids()
    runs = latest_runs(arm)
    agg = {b: dict(n=0, correct=0, abstained=0, wrong_confident=0, no_answer=0,
                   cost=0.0, seconds=0.0, tools=0) for b, _ in BENCHES}
    for tid, r in runs.items():
        b = _bench_of(tid, ids)
        if b is None or b not in agg:
            continue
        if restrict and b in ids and tid not in ids[b]:
            continue
        a = agg[b]
        a["n"] += 1
        o = r.get("outcome", "")
        if o in ("correct", "abstained", "wrong_confident", "no_answer"):
            a[o] += 1
        a["cost"] += r.get("cost_usd", 0) or 0
        a["seconds"] += r.get("seconds", 0) or 0
        a["tools"] += r.get("n_tool_calls", 0) or 0
    return agg


def pct(x, n):
    return (x / n * 100) if n else 0.0
