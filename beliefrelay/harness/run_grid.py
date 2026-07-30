"""Run the arm grid: {probe, homo, none} x pool tasks x k samples.

Resumable by (arm, task_id, sample). Budget-guarded: aborts if beliefrelay spend
crosses ABORT_AT_USD (spend.py, self-metered from the proxy log).

  conda run -n base python beliefrelay/harness/run_grid.py --arms probe,homo,none --k 2
  conda run -n base python beliefrelay/harness/run_grid.py --arms probe --limit 10  # smoke
"""
import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from relay import belief_sets_for, run_relay  # noqa: E402
from scoring import extract_answer, match_math  # noqa: E402
from spend import ABORT_AT_USD, total_spend  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(ROOT, "data", "tasks.jsonl")
POOL = os.path.join(ROOT, "pool.json")
BELIEFS = os.path.join(ROOT, "beliefs.json")
OUT = os.path.join(ROOT, "results", "grid.jsonl")

_write_lock = threading.Lock()
_spend_check = dict(n=0)


def check_budget():
    with _write_lock:
        _spend_check["n"] += 1
        n = _spend_check["n"]
    if n % 10 == 1:  # every 10th relay, read the log (cheap but not free)
        cost = total_spend()["cost_usd"]
        if cost > ABORT_AT_USD:
            raise SystemExit(f"BUDGET GUARD: ${cost:.2f} > ${ABORT_AT_USD} — aborting")


def one(task, ordinal, beliefs, arm, sample):
    check_budget()
    sets = belief_sets_for(arm, beliefs, ordinal)
    tag = f"br_grid_{arm}_{task['id']}_{sample}"
    res = run_relay(task, sets, tag)
    ans = extract_answer(res["final_message"])
    rec = dict(arm=arm, task_id=task["id"], sample=sample, answer=ans,
               correct=bool(match_math(ans, task["expected_answer"])),
               expected=task["expected_answer"], usage=res["usage"],
               belief_sets=sets, transcript=res["transcript"])
    with _write_lock:
        with open(OUT, "a") as f:
            f.write(json.dumps(rec) + "\n")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="probe,homo,none")
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="cap pool tasks (smoke)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    tasks = {json.loads(l)["id"]: json.loads(l) for l in open(TASKS)}
    pool = json.load(open(POOL))
    if args.limit:
        pool = pool[:args.limit]
    beliefs = json.load(open(BELIEFS))
    missing = [p["task_id"] for p in pool if p["task_id"] not in beliefs]
    if missing:
        raise SystemExit(f"no beliefs authored for: {missing}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT):
            try:
                r = json.loads(line)
                done.add((r["arm"], r["task_id"], r["sample"]))
            except Exception:  # noqa: BLE001
                continue

    jobs = []
    for arm in args.arms.split(","):
        for ordinal, p in enumerate(pool):
            for s in range(args.k):
                if (arm, p["task_id"], s) not in done:
                    jobs.append((tasks[p["task_id"]], ordinal,
                                 beliefs[p["task_id"]], arm, s))
    print(f"{len(jobs)} relays to run ({len(done)} already done); "
          f"spend so far ${total_spend()['cost_usd']:.2f}")
    n_ok = n_err = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(one, *j): (j[3], j[0]["id"], j[4]) for j in jobs}
        for fut in as_completed(futs):
            key = futs[fut]
            try:
                fut.result()
                n_ok += 1
                if n_ok % 10 == 0:
                    print(f"progress {n_ok}/{len(jobs)}", flush=True)
            except SystemExit as e:
                print(str(e), flush=True)
                ex.shutdown(cancel_futures=True)
                raise
            except Exception as e:  # noqa: BLE001
                n_err += 1
                print(f"ERROR {key}: {e}", flush=True)
    print(f"done: {n_ok} ok, {n_err} errors; spend ${total_spend()['cost_usd']:.2f}")


if __name__ == "__main__":
    main()
