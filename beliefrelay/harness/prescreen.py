"""Single-agent difficulty screen: k samples per MATH-L5 task at temp 0.7.

Output prescreen.jsonl, one line per (task, sample): {task_id, sample, answer,
correct, tokens}. Resumable — existing (task_id, sample) keys are skipped.

  conda run -n base python beliefrelay/harness/prescreen.py [--k 4] [--workers 8]
"""
import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import chat  # noqa: E402
from scoring import extract_answer, match_math  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(ROOT, "data", "tasks.jsonl")
OUT = os.path.join(ROOT, "results", "prescreen.jsonl")

SOLVER_SYS = (
    "You are solving a math problem. Work through it carefully and end your reply "
    "with a line of the form:\nFINAL ANSWER: <answer>"
)

_write_lock = threading.Lock()


def one(task, sample):
    out = chat(f"br_screen_{task['id']}_{sample}", [
        {"role": "system", "content": SOLVER_SYS},
        {"role": "user", "content": f"PROBLEM:\n{task['question']}"},
    ])
    ans = extract_answer(out["content"])
    rec = dict(task_id=task["id"], sample=sample, answer=ans,
               correct=bool(match_math(ans, task["expected_answer"])),
               finish=out.get("finish"),
               tokens=(out.get("usage") or {}).get("total_tokens", 0))
    with _write_lock:
        with open(OUT, "a") as f:
            f.write(json.dumps(rec) + "\n")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="cap tasks (smoke)")
    args = ap.parse_args()

    tasks = [json.loads(l) for l in open(TASKS)]
    if args.limit:
        tasks = tasks[:args.limit]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT):
            try:
                r = json.loads(line)
                done.add((r["task_id"], r["sample"]))
            except Exception:  # noqa: BLE001
                continue
    todo = [(t, s) for t in tasks for s in range(args.k)
            if (t["id"], s) not in done]
    print(f"{len(todo)} calls to run ({len(done)} already done)")
    n_ok = n_err = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(one, t, s): (t["id"], s) for t, s in todo}
        for fut in as_completed(futs):
            key = futs[fut]
            try:
                rec = fut.result()
                n_ok += 1
                if n_ok % 25 == 0:
                    print(f"progress {n_ok}/{len(todo)}", flush=True)
            except Exception as e:  # noqa: BLE001
                n_err += 1
                print(f"ERROR {key}: {e}", flush=True)
    print(f"done: {n_ok} ok, {n_err} errors")


if __name__ == "__main__":
    main()
