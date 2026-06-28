"""Live, precise cost tally for a running batch — reads shared/proxy/calls.jsonl
directly, so it counts EVERY completed upstream call the instant it lands, including
calls from tasks still mid-pipeline (the batch driver's running total only credits a
task once its result.json is written, so it lags; this does not).

Each 200-response logs prompt_tokens + completion_tokens; we price them at the
Tinker Qwen3.6-35B-A3B rates. Non-200 calls log `error=<status>` with NO token
fields (the proxy doesn't see usage on an upstream error), so any Tinker-side prefill
billed before a 4xx is invisible here — we surface the error COUNT so that blind spot
is at least flagged, never silent.

Usage:
  python camel/harness/cost_watch.py --since <epoch>                # one snapshot
  python camel/harness/cost_watch.py --since <epoch> --watch 20     # refresh every 20s
  python camel/harness/cost_watch.py --since <epoch> --cap 20       # WARN past $20
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
LOG = os.path.join(REPO_ROOT, "shared", "proxy", "calls.jsonl")

PREFILL = float(os.environ.get("CAMEL_PREFILL_RATE", 0.36))   # $/Mtok
SAMPLE = float(os.environ.get("CAMEL_SAMPLE_RATE", 0.89))     # $/Mtok


def _bench_of(tag):
    for b in ("gpqa", "math", "gaia"):
        if b in tag:
            return b
    return "other"


def snapshot(since):
    pt = ct = ok = err = 0
    by_bench = {}                     # bench -> [cost, n_ok, set(tasks)]
    by_status = {}                    # error status -> count
    by_task = {}                      # tag -> cost
    if os.path.exists(LOG):
        for line in open(LOG):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("ts", 0) < since:
                continue
            tag = r.get("tag", "")
            if not tag.startswith("camel_"):
                continue
            if r.get("error"):
                err += 1
                by_status[r["error"]] = by_status.get(r["error"], 0) + 1
                continue
            ok += 1
            p = r.get("prompt_tokens", 0) or 0
            c = r.get("completion_tokens", 0) or 0
            pt += p; ct += c
            cost = p / 1e6 * PREFILL + c / 1e6 * SAMPLE
            b = _bench_of(tag)
            slot = by_bench.setdefault(b, [0.0, 0, set()])
            slot[0] += cost; slot[1] += 1; slot[2].add(tag)
            by_task[tag] = by_task.get(tag, 0.0) + cost
    prefill_cost = pt / 1e6 * PREFILL
    sample_cost = ct / 1e6 * SAMPLE
    return dict(pt=pt, ct=ct, ok=ok, err=err, total=prefill_cost + sample_cost,
                prefill_cost=prefill_cost, sample_cost=sample_cost,
                by_bench=by_bench, by_status=by_status, by_task=by_task)


def render(s, since, cap):
    el = (time.time() - since) / 60
    lines = [
        f"── cost watch │ {el:.1f} min in │ {s['ok']} calls ok, {s['err']} err ──",
        f"  TOTAL ${s['total']:.3f}   (prefill ${s['prefill_cost']:.3f} / "
        f"sample ${s['sample_cost']:.3f})   tok {s['pt']:,}p + {s['ct']:,}c",
    ]
    for b in ("gpqa", "math", "gaia", "other"):
        if b in s["by_bench"]:
            cost, n, tasks = s["by_bench"][b]
            lines.append(f"    {b:6s} ${cost:6.3f}  {n:4d} calls  {len(tasks):3d} tasks")
    if s["by_status"]:
        lines.append(f"  errors by status: {s['by_status']}")
    top = sorted(s["by_task"].items(), key=lambda kv: -kv[1])[:5]
    if top:
        lines.append("  top tasks by cost:")
        for tag, c in top:
            lines.append(f"    ${c:5.3f}  {tag}")
    if cap and s["total"] >= cap:
        lines.append(f"  *** WARNING: ${s['total']:.2f} >= cap ${cap:.2f} — KILL THE BATCH ***")
    elif cap:
        lines.append(f"  (cap ${cap:.0f}; ${cap - s['total']:.2f} headroom)")
    return "\n".join(lines)


def main():
    a = sys.argv[1:]
    def opt(flag, default=None):
        return a[a.index(flag) + 1] if flag in a else default
    since = float(opt("--since", "0"))
    watch = opt("--watch")
    cap = float(opt("--cap")) if opt("--cap") else None
    if watch:
        while True:
            print("\033[2J\033[H" + render(snapshot(since), since, cap), flush=True)
            time.sleep(float(watch))
    else:
        print(render(snapshot(since), since, cap), flush=True)


if __name__ == "__main__":
    main()
