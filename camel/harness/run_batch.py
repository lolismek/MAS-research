"""Run the full sweep: every evaluated task across the 3 benchmarks through the CAMEL
pipeline, one arm, with a per-task USD cap and automatic RESUME.

RESUME is automatic and free: a task is "done" once it has a run_*/result.json, so
re-running the same command skips finished tasks and runs only what's missing —
nothing is re-spent. Crash-orphan run dirs (a run_* with no result.json) are pruned
before rerun so the trace tree stays clean.

PARALLELISM: --workers fans tasks out across threads, and the proxy DOES serve them
concurrently — MEASURED ~19x on the 357-task vanilla sweep (17.8h of summed per-task
wall-time finished in ~57 min). Default is 16. An earlier note here claimed the proxy
serialized to ~1x; that was wrong and is corrected. Because `conda run` buffers child
stdout until exit, a long parallel batch shows no streaming progress — watch the trace
dir (traces/<arm>/<id>/run_*/result.json) or shared/proxy/calls.jsonl instead.

Usage (repo root):
  conda run -n autogen_gc python camel/harness/run_batch.py                      # all 3, vanilla, 16-way, resume
  conda run -n autogen_gc python camel/harness/run_batch.py --benches gpqa_diamond --limit 5
  conda run -n autogen_gc python camel/harness/run_batch.py --workers 8 --budget 1.0   # throttle if needed
  conda run -n autogen_gc python camel/harness/run_batch.py --rerun-issues --workers 16  # only
       # tasks that BOTH hit a substrate limit (output cap / context overflow) AND did not
       # succeed; forces a fresh run that supersedes the old one (agg takes the latest run).
"""
import os, shutil, sys, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from run_task import run_one, resolve_tasks, load_tasks, pop_opt, TRACES, BUDGET_USD

BENCHES = ["gpqa_diamond", "math_l5", "gaia"]   # the evaluated sets


def _runs_dir(arm, tid):
    return os.path.join(TRACES, arm, tid)


def is_done(arm, tid):
    d = _runs_dir(arm, tid)
    return os.path.isdir(d) and any(
        os.path.exists(os.path.join(d, r, "result.json")) for r in os.listdir(d))


def prune_incomplete(arm, tid):
    """Drop crash-orphan run dirs (run_* with no result.json) so reruns stay clean."""
    d = _runs_dir(arm, tid)
    if not os.path.isdir(d):
        return
    for r in os.listdir(d):
        rd = os.path.join(d, r)
        if os.path.isdir(rd) and not os.path.exists(os.path.join(rd, "result.json")):
            shutil.rmtree(rd, ignore_errors=True)


def main():
    args = sys.argv[1:]
    rerun_issues = "--rerun-issues" in args
    force = "--force" in args or rerun_issues       # re-run even tasks that already have a result
    dry_run = "--dry-run" in args
    args = [a for a in args if a not in ("--rerun-issues", "--force", "--dry-run")]
    arm, args = pop_opt(args, "--arm"); arm = arm or "vanilla"
    benches, args = pop_opt(args, "--benches")
    workers, args = pop_opt(args, "--workers")
    limit, args = pop_opt(args, "--limit")
    budget, args = pop_opt(args, "--budget")
    # --tasks: run ONE curated file (e.g. hard_smoke.jsonl, the 9-task 3x3 subset the
    # add-on arms are evaluated on) instead of the per-bench sets. Tasks carry their own
    # `bench` field, so resume/agg/the viewer group them exactly as in a per-bench run.
    tasks_spec, args = pop_opt(args, "--tasks")
    bench_list = benches.split(",") if benches else BENCHES
    workers = int(workers) if workers else 16   # proxy serves ~19x concurrently (see module docstring)
    budget = float(budget) if budget else BUDGET_USD

    select_ids = None
    if rerun_issues:
        from rerun_select import select
        rr, _, _ = select(arm)
        select_ids = {t for t, _, _ in rr}
        print(f"--rerun-issues: {len(select_ids)} affected + non-successful tasks targeted "
              f"(forcing fresh runs that supersede the old ones)")

    todo, done_n = [], 0
    sources = [tasks_spec] if tasks_spec else bench_list
    for b in sources:
        tasks = load_tasks(resolve_tasks(b))
        if limit:
            tasks = tasks[:int(limit)]
        for t in tasks:
            if select_ids is not None and t["id"] not in select_ids:
                continue
            if (not force) and is_done(arm, t["id"]):
                done_n += 1
            else:
                prune_incomplete(arm, t["id"])     # keeps run_*/ that have result.json
                todo.append(t)

    total = done_n + len(todo)
    print(f"arm={arm} source={tasks_spec or ','.join(bench_list)} "
          f"budget=${budget:.2f}/task workers={workers}")
    print(f"{total} tasks | {done_n} already done (skipped) | {len(todo)} to run\n", flush=True)
    if not todo:
        print("nothing to run — all done.")
        return
    if dry_run:
        print("--dry-run: would run these tasks:\n  " +
              ", ".join(t["id"] for t in todo))
        return

    t0, tally, cost, n = time.time(), Counter(), 0.0, 0
    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(run_one, t, arm, budget): t for t in todo}
            for fut in as_completed(futs):
                r = fut.result()
                n += 1
                tally[r["outcome"]] += 1
                cost += r.get("cost_usd", 0) or 0
                print(f"  >> {n}/{len(todo)} | correct={tally['correct']} "
                      f"abstained={tally['abstained']} wrong={tally['wrong_confident']} "
                      f"| ${cost:.2f} so far", flush=True)
    except KeyboardInterrupt:
        print("\ninterrupted — finished tasks are saved; rerun the same command to resume.",
              flush=True)

    print(f"\n=== ran {n}/{len(todo)} in {(time.time()-t0)/60:.1f} min | "
          f"${cost:.2f} | {dict(tally)} ===")


if __name__ == "__main__":
    main()
