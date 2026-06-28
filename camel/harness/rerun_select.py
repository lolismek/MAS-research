"""Select tasks worth re-running after the cap/compaction fixes: a task qualifies only
if it BOTH (a) suffered a substrate issue — an agent call hit the 8192 output cap, or
the prompt overflowed context (HTTP 400 / prompt>55k) — AND (b) did not already succeed
(outcome != correct). That intersection is the point: an affected-but-correct task worked
despite truncation (leave it), and an unaffected wrong answer is a genuine capability miss
(re-running won't change it at temperature 0). Reads the per-call proxy log + traces.

  python camel/harness/rerun_select.py            # print the set + the excluded misses
  python camel/harness/rerun_select.py --ids       # just the ids, comma-separated (for --tasks-file)
"""
import json, os, glob, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agg  # noqa: E402

ROOT = os.path.dirname(HERE)
TRACES = os.path.join(ROOT, "traces")
CALLS = os.path.join(os.path.dirname(ROOT), "shared", "proxy", "calls.jsonl")
CAP_HIT = 8000          # a call with completion_tokens >= this hit the 8192 output cap
PROMPT_WALL = 55000     # prompt this large was near the 64k context wall


def _latest_runs(arm):
    latest = {}
    for f in glob.glob(os.path.join(TRACES, arm, "*", "run_*", "result.json")):
        tid = os.path.basename(os.path.dirname(os.path.dirname(f)))
        rn = int(f.split("run_")[1].split(os.sep)[0])
        if tid not in latest or rn > latest[tid][0]:
            latest[tid] = (rn, f)
    return latest


def select(arm="vanilla"):
    ids = agg.eval_ids()
    latest = _latest_runs(arm)

    def in_eval(tid):
        b = agg._bench_of(tid, ids)
        return b is not None and (b not in ids or tid in ids[b])

    # per-(tid) call signals from the proxy log, restricted to the latest run
    sig = defaultdict(lambda: dict(cap=False, overflow=False))
    for line in open(CALLS):
        try:
            r = json.loads(line)
        except Exception:
            continue
        tag = str(r.get("tag", ""))
        if not tag.startswith(f"camel_{arm}_") or "_run" not in tag:
            continue
        tid, rn = tag[len(f"camel_{arm}_"):].rsplit("_run", 1)
        try:
            rn = int(rn)
        except ValueError:
            continue
        if not in_eval(tid) or tid not in latest or latest[tid][0] != rn:
            continue
        if r.get("error"):
            if "400" in str(r.get("error")):
                sig[tid]["overflow"] = True
            continue
        if (r.get("completion_tokens", 0) or 0) >= CAP_HIT:
            sig[tid]["cap"] = True
        if (r.get("prompt_tokens", 0) or 0) > PROMPT_WALL:
            sig[tid]["overflow"] = True

    rerun, excluded_unaffected, affected_ok = [], [], []
    for tid, (rn, f) in latest.items():
        if not in_eval(tid):
            continue
        outcome = json.load(open(f)).get("outcome")
        affected = sig[tid]["cap"] or sig[tid]["overflow"]
        if outcome == "correct":
            if affected:
                affected_ok.append(tid)
            continue
        if affected:
            rerun.append((tid, outcome, "overflow" if sig[tid]["overflow"] else "cap"))
        else:
            excluded_unaffected.append((tid, outcome))   # genuine miss, no issue to fix
    return rerun, excluded_unaffected, affected_ok


def main():
    rerun, excluded, affected_ok = select("vanilla")
    if "--ids" in sys.argv:
        print(",".join(sorted(t for t, _, _ in rerun)))
        return
    by_b = defaultdict(list)
    for tid, oc, why in rerun:
        by_b[agg._bench_of(tid, agg.eval_ids())].append((tid, oc, why))
    print(f"RE-RUN SET — affected AND non-successful: {len(rerun)} tasks")
    for b, _ in agg.BENCHES:
        items = sorted(by_b.get(b, []))
        if not items:
            continue
        print(f"\n  {b} ({len(items)}):")
        for tid, oc, why in items:
            print(f"     {tid:16s} {oc:15s} [{why}]")
    print(f"\nEXCLUDED — non-successful but NOT affected (genuine misses, re-run won't help): "
          f"{len(excluded)}")
    for tid, oc in sorted(excluded):
        print(f"     {tid:16s} {oc}")
    print(f"\nFYI — affected but already correct (left as-is): {len(affected_ok)} tasks")


if __name__ == "__main__":
    main()
