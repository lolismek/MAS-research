"""Grid runner: tasks x N x arm, parallel, resumable, with a live summary.

  conda run -n autogen_gc python chainloss/harness/run_batch.py \\
      --tasks fanoutqa.jsonl --ns 1,2,4,8 --arms note,transcript --workers 4

Jobs are (task, n, arm) cells. Results append to chainloss/sweeps/<name>/results.jsonl
as they land; a re-run SKIPS cells already present there (resume = just relaunch).
--limit caps tasks (first K of the file, stable). The summary table (mean recall /
exact / abstain by arm x N) prints at the end and writes summary.md.
"""
import json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed

from run_task import run_one, resolve_tasks, load_tasks, pop_opt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SWEEPS = os.path.join(ROOT, "sweeps")

_write_lock = threading.Lock()


def _done_cells(results_path):
    done = set()
    if os.path.exists(results_path):
        for line in open(results_path):
            try:
                r = json.loads(line)
                done.add((r["id"], r["n"], r["arm"]))
            except Exception:
                continue
    return done


def _summary(results):
    cells = {}
    for r in results:
        cells.setdefault((r["arm"], r["n"]), []).append(r)
    lines = ["| arm | N | n_tasks | recall | exact | abstained | no_answer | "
             "note_yield | ctok/run | $/run |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for (arm, n), rs in sorted(cells.items()):
        recs = [r["recall"] for r in rs if r.get("recall") is not None]
        ny = [r["note_yield"] for r in rs if r.get("note_yield") is not None]
        mean = lambda xs: sum(xs) / len(xs) if xs else None
        fmt = lambda v, p="{:.3f}": p.format(v) if v is not None else "—"
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            arm, n, len(rs), fmt(mean(recs)),
            fmt(mean([1.0 if r["exact_match"] else 0.0 for r in rs])),
            fmt(mean([1.0 if r["outcome"] == "abstained" else 0.0 for r in rs])),
            fmt(mean([1.0 if r["outcome"] == "no_answer" else 0.0 for r in rs])),
            fmt(mean(ny)),
            fmt(mean([r["completion_tokens"] for r in rs]), "{:.0f}"),
            fmt(mean([r["cost_usd"] for r in rs]), "{:.3f}")))
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    spec, args = pop_opt(args, "--tasks"); spec = spec or "fanoutqa.jsonl"
    ns, args = pop_opt(args, "--ns"); ns = [int(x) for x in (ns or "1,2,4,8").split(",")]
    arms, args = pop_opt(args, "--arms"); arms = (arms or "note,transcript").split(",")
    budget, args = pop_opt(args, "--budget"); budget = int(budget) if budget else None
    limit, args = pop_opt(args, "--limit")
    workers, args = pop_opt(args, "--workers"); workers = int(workers) if workers else 4
    name, args = pop_opt(args, "--name")
    name = name or f"sweep_{time.strftime('%Y%m%d_%H%M')}"

    tasks = load_tasks(resolve_tasks(spec))
    if limit:
        tasks = tasks[:int(limit)]
    sweep_dir = os.path.join(SWEEPS, name)
    os.makedirs(sweep_dir, exist_ok=True)
    results_path = os.path.join(sweep_dir, "results.jsonl")
    done = _done_cells(results_path)

    jobs = [(t, n, arm) for arm in arms for n in ns for t in tasks
            if (t["id"], n, arm) not in done]
    print(f"[{name}] {len(jobs)} jobs ({len(done)} already done), workers={workers}",
          flush=True)

    def _job(t, n, arm):
        r = run_one(t, n=n, arm=arm, total_budget=budget)
        with _write_lock:
            with open(results_path, "a") as f:
                f.write(json.dumps(r) + "\n")
        return r

    failed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_job, t, n, arm): (t["id"], n, arm) for t, n, arm in jobs}
        for fut in as_completed(futs):
            tid, n, arm = futs[fut]
            try:
                fut.result()
            except Exception as e:
                failed += 1
                print(f"[FAIL {arm}/n{n}/{tid}] {e!r}", flush=True)

    all_results = [json.loads(l) for l in open(results_path)] if os.path.exists(results_path) else []
    table = _summary(all_results)
    with open(os.path.join(sweep_dir, "summary.md"), "w") as f:
        f.write(f"# {name}\n\n{table}\n")
    spent = sum(r["cost_usd"] for r in all_results)
    print(f"\n{table}\n\n[{name}] done: {len(all_results)} results, {failed} failed, "
          f"total ${spent:.2f}", flush=True)


if __name__ == "__main__":
    main()
