"""Run the relay or the single-agent ceiling on tasks; score; write traces.

  python lip/harness/run_task.py --arm relay   --n 4 --k 5  --runs 3 frames_100
  python lip/harness/run_task.py --arm ceiling --n 1 --k 20 --runs 3 --all --workers 8 --skip-done
Traces: lip/traces/<arm>/<task_id>/run_<r>/run.json
"""
import argparse, json, os, sys, time, traceback
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from llm import TinkerChat, spend, BudgetExceeded, current_cap, exp_spent
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
        f.write(f"gold: {tr['gold']}\ncorrect: {tr.get('correct')} ({(tr.get('score') or {}).get('reason')})\n")

HOLDERS = {"none": lambda N: (), "first": lambda N: (1,), "last": lambda N: (N,), "all": lambda N: tuple(range(1, N + 1)),
           "second": lambda N: (2,), "from_second": lambda N: tuple(range(2, N + 1))}   # agent 1 works without the belief

# two-atom experiment: {arm: fn(N) -> {agent: which atoms}}; "1" = the atom for the EARLIER holder (task["first_atom"]), "2" = the other
ATOM_ARMS = {"none": lambda N: {}, "both1": lambda N: {1: "12"}, "split_adj": lambda N: {1: "1", 2: "2"},
             "split_far": lambda N: {1: "1", 4: "2"}, "all": lambda N: {i: "12" for i in range(1, N + 1)}}
ATOM_MIN_FINISH = 4   # nobody may finish before agent 4 (split_far's second holder), in every two-atom arm

def atom_briefings(task, atom_arm, N):
    """{agent: briefing text} for a two-atom task (beliefs of the atoms that agent holds, earlier-holder atom first)."""
    by_key = {a["key"]: a["belief"] for a in task["atoms"]}
    order = {"1": task["first_atom"], "2": "B" if task["first_atom"] == "A" else "A"}
    return {i: "\n".join(by_key[order[c]] for c in cs) for i, cs in ATOM_ARMS[atom_arm](N).items()}

def one(task, arm, N, K, r, chat, corpus, holder=None, atom_arm=None):
    run_dir = os.path.join(TRACES, arm, task["id"], f"run_{r}")
    tag = f"{arm}/{task['id']}/r{r}"
    try:
        prev = _judge_pending(os.path.join(run_dir, "run.json"))
        if prev is not None:   # relay already ran, only the judge failed: rescore, don't rerun
            tr = prev
        elif atom_arm is not None:   # two-atom arm: both qualifiers stripped, beliefs spread per ATOM_ARMS
            tr = run_relay(task, N, K, chat, corpus, tag, briefings=atom_briefings(task, atom_arm, N), min_finish=ATOM_MIN_FINISH)
            tr["atom_arm"] = atom_arm; tr["first_atom"] = task["first_atom"]; tr["original_question"] = task.get("original_question")
        elif holder is None:
            tr = run_relay(task, N, K, chat, corpus, tag)
        else:   # internal-belief arm: stripped question in task["question"], belief in task["belief"]
            tr = run_relay(task, N, K, chat, corpus, tag, briefing=task["belief"], holders=HOLDERS[holder](N))
            tr["holder"] = holder; tr["original_question"] = task.get("original_question")
        tr["arm"] = arm; tr["run"] = r
        try:
            sc = score(task.get("original_question") or task["question"], task["answer"], tr["final"] or "", tag=f"judge/{tag}")
        except BudgetExceeded:
            raise
        except Exception:   # judge/API failure: keep the paid-for trace, mark for rescoring
            tr["score"] = None; tr["correct"] = None; tr["error"] = "judge: " + traceback.format_exc()[-800:]
            save(run_dir, tr); return tr
        tr["score"] = sc; tr["correct"] = sc["correct"]; tr["error"] = None
    except BudgetExceeded as e:
        return dict(task_id=task["id"], gold=task["answer"], arm=arm, run=r, agents=[], final=None, correct=None,
                    error=f"BudgetExceeded: {e}", N=N, K=K, unsaved=True)      # not saved: re-runnable
    except Exception as e:
        tr = dict(task_id=task["id"], gold=task["answer"], arm=arm, run=r, agents=[], final=None, correct=None,
                  error=traceback.format_exc()[-2000:], N=N, K=K)
    save(run_dir, tr)
    return tr

def _judge_pending(path):
    """saved trace whose relay finished but whose judge call failed (error 'judge: ...'), else None."""
    try: d = json.load(open(path))
    except Exception: return None
    return d if d.get("agents") and str(d.get("error") or "").startswith("judge:") else None

def _done(path):
    """run.json exists and holds a completed (error-free) run."""
    if not os.path.exists(path): return False
    try: return json.load(open(path)).get("error") is None
    except Exception: return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--arm", default="relay"); ap.add_argument("--n", type=int, default=4); ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--runs", type=int, default=1); ap.add_argument("--all", action="store_true")
    ap.add_argument("--tasks", default=os.path.join(DATA, "tasks_screened.jsonl"))
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--holder", choices=sorted(HOLDERS), default=None,
                    help="internal-belief experiment: who gets the task's belief as a private briefing (needs --tasks tasks_internal.jsonl)")
    ap.add_argument("--atom-arm", choices=sorted(ATOM_ARMS), default=None,
                    help="two-atom experiment: who holds which belief (needs --tasks tasks_internal_2atom.jsonl); arm dir int2_<atom-arm>")
    ap.add_argument("--skip-done", action="store_true"); ap.add_argument("--budget", type=float, default=5.0,
                    help="stop launching new runs once total logged spend exceeds this many USD")
    a = ap.parse_args()
    if a.holder and a.arm == "relay": a.arm = f"internal_{a.holder}"
    if a.atom_arm and a.arm == "relay": a.arm = f"int2_{a.atom_arm}"
    tasks = load_tasks(a.tasks)
    if a.atom_arm: assert all("atoms" in t for t in tasks.values()), "--atom-arm needs tasks_internal_2atom.jsonl"
    if a.holder: assert all("belief" in t for t in tasks.values()), "--holder needs a tasks file with a `belief` field"
    ids = list(tasks) if a.all else a.ids
    if a.limit: ids = ids[:a.limit]
    jobs = [(tasks[i], r) for i in ids for r in range(1, a.runs + 1)]
    if a.skip_done:   # skip finished runs; errored runs (harness/API failure) are re-done
        jobs = [(t, r) for t, r in jobs if not _done(os.path.join(TRACES, a.arm, t["id"], f"run_{r}", "run.json"))]
    print(f"{a.arm} N={a.n} K={a.k} holder={a.holder} atom_arm={a.atom_arm}: {len(jobs)} runs, workers={a.workers}, budget ${a.budget}", flush=True)
    chat, corpus = TinkerChat(), Corpus.get()
    t0 = time.time(); done = 0; correct = 0; spend0 = spend(a.arm + "/")   # this arm's own tags only (parallel arms share the log)

    def job(tr_):
        t, r = tr_
        try:
            if spend(a.arm + "/") - spend0 > a.budget or (current_cap() and spend() >= current_cap()): return None
            if exp_spent(): return None
            return one(t, a.arm, a.n, a.k, r, chat, corpus, holder=a.holder, atom_arm=a.atom_arm)
        except Exception:
            return dict(task_id=t["id"], gold=t["answer"], run=r, error=traceback.format_exc()[-500:], unsaved=True)

    with ThreadPoolExecutor(a.workers) as ex:
        for tr in ex.map(job, jobs):
            if tr is None: print("budget reached, skipping remaining", flush=True); continue
            if tr.get("unsaved"): print(f"  UNSAVED {tr['task_id']} r{tr.get('run')}: {tr['error'][-160:]!r}", flush=True); continue
            done += 1; correct += bool(tr.get("correct"))
            fb = tr.get("finished_by"); err = "ERROR " if tr.get("error") else ""
            print(f"  {err}{tr['task_id']} r{tr.get('run')} -> {str(tr.get('final'))[:40]!r} | gold {tr['gold'][:30]!r} | "
                  f"{'OK' if tr.get('correct') else 'x'} | by a{fb} | ${tr.get('cost', 0):.3f} {tr.get('seconds', 0)}s "
                  f"| total ${spend():.2f}", flush=True)
    print(f"done {done} runs, {correct} correct, {time.time()-t0:.0f}s, spend ${spend():.2f}", flush=True)

if __name__ == "__main__":
    main()
