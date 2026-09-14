"""Run the relay or the single-agent ceiling on tasks; score; write traces.

  python lip/harness/run_task.py --arm relay   --n 4 --k 5  --runs 3 frames_100
  python lip/harness/run_task.py --arm ceiling --n 1 --k 20 --runs 3 --all --workers 8 --skip-done
Traces: lip/traces/<arm>/<task_id>/run_<r>/run.json
"""
import argparse, json, os, sys, time, traceback
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from llm import TinkerChat, spend
from tools import Corpus
from relay import run_relay
from judge import score

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRACES = os.path.join(ROOT, "lip", "traces")
DATA = os.path.join(ROOT, "lip", "data")

def load_tasks(path):
    return {t["id"]: t for t in (json.loads(l) for l in open(path))}

def save(run_dir, tr):
    os.makedirs(run_dir, exist_ok=True)
    json.dump(tr, open(os.path.join(run_dir, "run.json"), "w"), indent=1, ensure_ascii=False)
    with open(os.path.join(run_dir, "handoffs.txt"), "w") as f:
        for a in tr["agents"]:
            f.write(f"===== agent {a['agent']} (calls {a['tool_calls_used']}, opened {a['opened']}) =====\n")
            if a["handoff"] is not None: f.write(a["handoff"] + "\n\n")
            if a["final"] is not None: f.write(f"FINAL: {a['final']}\n\n")
        f.write(f"gold: {tr['gold']}\ncorrect: {tr.get('correct')} ({tr.get('score', {}).get('reason')})\n")

HOLDERS = {"none": lambda N: (), "first": lambda N: (1,), "last": lambda N: (N,), "all": lambda N: tuple(range(1, N + 1))}

def one(task, arm, N, K, r, chat, corpus, holder=None):
    run_dir = os.path.join(TRACES, arm, task["id"], f"run_{r}")
    tag = f"{arm}/{task['id']}/r{r}"
    try:
        if holder is None:
            tr = run_relay(task, N, K, chat, corpus, tag)
        else:   # internal-belief arm: stripped question in task["question"], belief in task["belief"]
            tr = run_relay(task, N, K, chat, corpus, tag, briefing=task["belief"], holders=HOLDERS[holder](N))
            tr["holder"] = holder; tr["original_question"] = task.get("original_question")
        sc = score(task.get("original_question") or task["question"], task["answer"], tr["final"] or "", tag=f"judge/{tag}")
        tr["score"] = sc; tr["correct"] = sc["correct"]; tr["arm"] = arm; tr["run"] = r; tr["error"] = None
    except Exception as e:
        tr = dict(task_id=task["id"], gold=task["answer"], arm=arm, run=r, agents=[], final=None, correct=None,
                  error=traceback.format_exc()[-2000:], N=N, K=K)
    save(run_dir, tr)
    return tr

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--arm", default="relay"); ap.add_argument("--n", type=int, default=4); ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--runs", type=int, default=1); ap.add_argument("--all", action="store_true")
    ap.add_argument("--tasks", default=os.path.join(DATA, "tasks_screened.jsonl"))
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--holder", choices=sorted(HOLDERS), default=None,
                    help="internal-belief experiment: who gets the task's belief as a private briefing (needs --tasks tasks_internal.jsonl)")
    ap.add_argument("--skip-done", action="store_true"); ap.add_argument("--budget", type=float, default=5.0,
                    help="stop launching new runs once total logged spend exceeds this many USD")
    a = ap.parse_args()
    if a.holder and a.arm == "relay": a.arm = f"internal_{a.holder}"
    tasks = load_tasks(a.tasks)
    if a.holder: assert all("belief" in t for t in tasks.values()), "--holder needs a tasks file with a `belief` field"
    ids = list(tasks) if a.all else a.ids
    if a.limit: ids = ids[:a.limit]
    jobs = [(tasks[i], r) for i in ids for r in range(1, a.runs + 1)]
    if a.skip_done:
        jobs = [(t, r) for t, r in jobs if not os.path.exists(os.path.join(TRACES, a.arm, t["id"], f"run_{r}", "run.json"))]
    print(f"{a.arm} N={a.n} K={a.k} holder={a.holder}: {len(jobs)} runs, workers={a.workers}, budget ${a.budget}", flush=True)
    chat, corpus = TinkerChat(), Corpus.get()
    t0 = time.time(); done = 0; correct = 0; spend0 = spend()

    def job(tr_):
        t, r = tr_
        if spend() - spend0 > a.budget: return None
        return one(t, a.arm, a.n, a.k, r, chat, corpus, holder=a.holder)

    with ThreadPoolExecutor(a.workers) as ex:
        for tr in ex.map(job, jobs):
            if tr is None: print("budget reached, skipping remaining", flush=True); continue
            done += 1; correct += bool(tr.get("correct"))
            fb = tr.get("finished_by"); err = "ERROR " if tr.get("error") else ""
            print(f"  {err}{tr['task_id']} r{tr.get('run')} -> {str(tr.get('final'))[:40]!r} | gold {tr['gold'][:30]!r} | "
                  f"{'OK' if tr.get('correct') else 'x'} | by a{fb} | ${tr.get('cost', 0):.3f} {tr.get('seconds', 0)}s "
                  f"| total ${spend():.2f}", flush=True)
    print(f"done {done} runs, {correct} correct, {time.time()-t0:.0f}s, spend ${spend():.2f}", flush=True)

if __name__ == "__main__":
    main()
