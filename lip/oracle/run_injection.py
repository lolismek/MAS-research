"""Injection experiment driver.

For each task with a failed vanilla relay run (first failed run), run the oracle once, then resample the suffix
(agents i..N) M times under each condition. Traces: lip/traces/inj/<task>/oracle.json and
lip/traces/inj/<task>/<cond>/run_<m>/run.json.

  python lip/oracle/run_injection.py frames_100                # one task
  python lip/oracle/run_injection.py --all --m 3 --workers 6 --skip-done
"""
import argparse, json, os, sys, traceback
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
sys.path.insert(0, os.path.dirname(__file__))
from llm import TinkerChat, spend, BudgetExceeded, current_cap
from tools import Corpus
from relay import run_relay
from judge import score
from enhance import enhance, conditions
from run_task import save, TRACES, DATA, load_tasks, _done

CONDS = ["enhanced", "original", "random", "passthrough"]

def failed_run(task_id, arm="relay"):
    d = os.path.join(TRACES, arm, task_id)
    if not os.path.isdir(d): return None
    for r in sorted(os.listdir(d)):
        p = os.path.join(d, r, "run.json")
        if os.path.exists(p):
            tr = json.load(open(p))
            if tr.get("correct") is False and not tr.get("error") and len(tr["agents"]) >= 2: return tr
    return None

def run_one(task, M, chat, corpus, conds, skip_done, arm="relay", out="inj"):
    base = os.path.join(TRACES, out, task["id"]); os.makedirs(base, exist_ok=True)
    tr = failed_run(task["id"], arm)
    if tr is None: return dict(id=task["id"], skipped="no failed run with >=2 agents")
    op = os.path.join(base, "oracle.json")
    if os.path.exists(op) and skip_done:
        oo = json.load(open(op))
    else:
        oo = enhance(tr, tag=f"oracle/{task['id']}")
        oo["source_run"] = tr.get("run"); json.dump(oo, open(op, "w"), indent=1, ensure_ascii=False)
    if oo.get("declined"):
        return dict(id=task["id"], skipped="oracle declined: " + str(oo.get("why"))[:160], cost=oo.get("cost", 0))
    if not oo.get("i") or not oo.get("kept_text"):
        return dict(id=task["id"], skipped=f"oracle: i={oo.get('i')} kept={oo.get('n_kept')}", cost=oo.get("cost", 0))
    cm = conditions(tr, oo)
    json.dump(cm, open(os.path.join(base, "conditions.json"), "w"), indent=1, ensure_ascii=False)
    i = cm["i"]; res = {}
    for cond in conds:
        res[cond] = []
        for m in range(1, M + 1):
            rd = os.path.join(base, cond, f"run_{m}")
            if skip_done and _done(os.path.join(rd, "run.json")):
                res[cond].append(json.load(open(os.path.join(rd, "run.json"))).get("correct")); continue
            tag = f"inj/{task['id']}/{cond}/r{m}"
            try:
                t2 = run_relay(task, tr["N"], tr["K"], chat, corpus, tag, incoming=cm[cond], start_agent=i,
                               prefix_agents=tr["agents"][:i - 1])
                sc = score(task["question"], task["answer"], t2["final"] or "", tag=f"judge/{tag}")
                t2.update(score=sc, correct=sc["correct"], arm=f"inj/{cond}", run=m, error=None, condition=cond, i=i)
            except BudgetExceeded as e:
                return dict(id=task["id"], i=i, skipped=f"budget: {e}", results=res)     # run not saved: re-runnable
            except Exception:
                t2 = dict(task_id=task["id"], gold=task["answer"], arm=f"inj/{cond}", run=m, agents=[], final=None,
                          correct=None, error=traceback.format_exc()[-2000:], condition=cond, i=i)
            save(rd, t2); res[cond].append(t2.get("correct"))
    return dict(id=task["id"], i=i, n_kept=oo.get("n_kept"), results=res)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--m", type=int, default=3); ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--conds", default=",".join(CONDS)); ap.add_argument("--skip-done", action="store_true")
    ap.add_argument("--tasks", default=os.path.join(DATA, "tasks_screened.jsonl")); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", type=float, default=5.0)
    ap.add_argument("--arm", default="relay", help="arm whose failed runs are the source traces")
    ap.add_argument("--out", default="inj", help="traces subdir for this injection experiment")
    a = ap.parse_args()
    tasks = load_tasks(a.tasks)
    ids = [t for t in tasks if failed_run(t, a.arm)] if a.all else a.ids
    if a.limit: ids = ids[:a.limit]
    conds = a.conds.split(",")
    print(f"injection: {len(ids)} tasks, M={a.m}, conds={conds}", flush=True)
    chat, corpus = TinkerChat(), Corpus.get(); spend0 = spend()
    def job(tid):
        try:
            if spend() - spend0 > a.budget or (current_cap() and spend() >= current_cap()): return dict(id=tid, skipped="budget")
            return run_one(tasks[tid], a.m, chat, corpus, conds, a.skip_done, a.arm, a.out)
        except Exception:
            return dict(id=tid, error=traceback.format_exc()[-400:])
    with ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(job, ids):
            print("  " + json.dumps(r) + f"  | total ${spend():.2f}", flush=True)

if __name__ == "__main__":
    main()
