"""Re-score saved runs with the current judge backend (LIP_JUDGE). Exact-match/empty finals are untouched; runs whose
previous verdict came from an LLM judge are re-judged (old verdict kept in score['judge_prev']); runs whose judge call
failed (error 'judge: ...') get scored for the first time. Rewrites run.json + handoffs.txt.

  python lip/internal/rejudge.py --arms internal_none internal_first internal_all --workers 12
"""
import argparse, json, os, sys, glob
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
from judge import score, JUDGE_MODEL, exact_match
from run_task import save, TRACES, load_tasks, DATA

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True); ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--tasks", default=os.path.join(DATA, "tasks_internal.jsonl"))
    a = ap.parse_args(); tasks = load_tasks(a.tasks)
    paths = [p for arm in a.arms for p in sorted(glob.glob(os.path.join(TRACES, arm, "*", "run_*", "run.json")))]
    def job(p):
        tr = json.load(open(p))
        if not tr.get("agents"): return ("skip-error", None, None)
        sc = tr.get("score") or {}
        pending = str(tr.get("error") or "").startswith("judge:") or not sc
        if not pending and (sc.get("em") or sc.get("judge") is None): return ("em-or-empty", None, None)
        if not pending and sc.get("model") == JUDGE_MODEL: return ("already", None, None)
        t = tasks[tr["task_id"]]
        new = score(t.get("original_question") or t["question"], t["answer"], tr["final"] or "", tag=f"judge/{tr['arm']}/{tr['task_id']}/r{tr['run']}")
        prev = None if pending else f"{sc.get('model') or 'openai/gpt-5.4-mini'}:{sc['judge']}"
        if prev: new["judge_prev"] = prev
        tr["score"] = new; tr["correct"] = new["correct"]; tr["error"] = None
        save(os.path.dirname(p), tr)
        return ("rejudged" if prev else "scored", prev, new["judge"])
    from collections import Counter
    c = Counter(); agree = dis = 0
    with ThreadPoolExecutor(a.workers) as ex:
        for kind, prev, new in ex.map(job, paths):
            c[kind] += 1
            if prev: agree += prev.split(":")[1] == new; dis += prev.split(":")[1] != new
    print(f"judge {JUDGE_MODEL}: {dict(c)}; re-judged agreement {agree}/{agree+dis}")

if __name__ == "__main__":
    main()
