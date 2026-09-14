"""Summaries over traces.

  python lip/metrics/summarize.py                 # per-arm accuracy, cost, budget exhaustion, found-but-lost
  python lip/metrics/summarize.py --inj           # injection conditions, paired by task

Found-but-lost (mechanical): for each gold page of a task, which agent(s) opened it, and whether the handoff
of each such agent mentions it (page title, or the last word of the title, case-insensitive).
"""
import argparse, glob, json, os, re, sys
from collections import defaultdict
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "data"))
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRACES = os.path.join(ROOT, "lip", "traces"); DATA = os.path.join(ROOT, "lip", "data")

def gold_title_map():
    """requested title (from the FRAMES url) -> resolved page title, from the corpus gold records."""
    m = {}
    for fn in glob.glob(os.path.join(DATA, "corpus", "gold", "*.json")):
        r = json.load(open(fn))
        if not r.get("missing"): m[r["requested"]] = r["title"]
    return m

def url_to_title(u):
    from urllib.parse import unquote
    t = unquote(u.split("/wiki/", 1)[1]) if "/wiki/" in u else u
    return t.split("#")[0].replace("_", " ").strip()

def load_runs(arm):
    out = []
    for p in sorted(glob.glob(os.path.join(TRACES, arm, "*", "run_*", "run.json"))):
        out.append(json.load(open(p)))
    return out

def norm(s): return re.sub(r"\s+", " ", (s or "").lower()).strip()

def mentions(text, title):
    t = norm(text); ti = norm(title)
    if not t or not ti: return False
    if ti in t: return True
    last = ti.split()[-1]
    return len(last) > 3 and last in t

def found_but_lost(tr, gold_titles):
    """Per gold page: opened_by (agents), lost_at (agents that opened it and whose handoff lacks it), never_found."""
    res = []
    for g in gold_titles:
        opened_by = [a["agent"] for a in tr["agents"] if any(norm(o) == norm(g) for o in a["opened"])]
        lost_at = [a["agent"] for a in tr["agents"] if a["agent"] in opened_by and a["handoff"] is not None and not mentions(a["handoff"], g)]
        res.append(dict(title=g, opened_by=opened_by, lost_at=lost_at))
    return res

def summarize_arms(arms):
    tasks = {t["id"]: t for t in (json.loads(l) for l in open(os.path.join(DATA, "tasks.jsonl")))}
    gmap = gold_title_map()
    for arm in arms:
        runs = [r for r in load_runs(arm) if not r.get("error")]
        errs = len(load_runs(arm)) - len(runs)
        if not runs: print(f"{arm}: no runs"); continue
        by_task = defaultdict(list)
        for r in runs: by_task[r["task_id"]].append(r)
        acc = sum(bool(r["correct"]) for r in runs) / len(runs)
        maj = sum(sum(bool(x["correct"]) for x in v) * 2 > len(v) for v in by_task.values()) / len(by_task)
        anyc = sum(any(x["correct"] for x in v) for v in by_task.values()) / len(by_task)
        cost = sum(r.get("cost", 0) for r in runs); secs = sum(r.get("seconds", 0) for r in runs) / len(runs)
        fin_by = defaultdict(int)
        for r in runs: fin_by[r.get("finished_by")] += 1
        exhausted = sum(1 for r in runs if r.get("finished_by") == r["N"] and r["agents"][-1]["tool_calls_used"] >= r["K"]) / len(runs)
        print(f"{arm}: {len(runs)} runs ({errs} errors), {len(by_task)} tasks | acc {acc:.3f} | task-majority {maj:.3f} | any {anyc:.3f} "
              f"| finished_by {dict(fin_by)} | last-agent-forced {exhausted:.2f} | ${cost:.2f} | {secs:.0f}s/run")
        # found-but-lost
        n_gold = n_found = n_lost_any = 0; tasks_all_found = tasks_fail = tasks_fail_allfound = 0
        for r in runs:
            t = tasks.get(r["task_id"]);
            if not t: continue
            gts = [gmap.get(url_to_title(u), url_to_title(u)) for u in t["gold_links"]]
            fbl = found_but_lost(r, gts)
            n_gold += len(fbl); n_found += sum(bool(x["opened_by"]) for x in fbl); n_lost_any += sum(bool(x["lost_at"]) for x in fbl)
            allf = all(x["opened_by"] for x in fbl)
            tasks_all_found += allf
            if not r["correct"]: tasks_fail += 1; tasks_fail_allfound += allf
        if n_gold:
            print(f"   gold pages: {n_gold} | opened by some agent {n_found/n_gold:.2f} | opened-then-absent-from-handoff {n_lost_any/n_gold:.2f} "
                  f"| runs with all gold opened {tasks_all_found/len(runs):.2f} | failed runs with all gold opened {tasks_fail_allfound}/{tasks_fail}")

def summarize_inj():
    from collections import Counter
    rows = defaultdict(dict)
    for p in glob.glob(os.path.join(TRACES, "inj", "*", "*", "run_*", "run.json")):
        r = json.load(open(p))
        if r.get("error"): continue
        rows[r["task_id"]].setdefault(r["condition"], []).append(bool(r["correct"]))
    conds = ["original", "enhanced", "random", "passthrough"]
    print(f"injection: {len(rows)} tasks")
    for c in conds:
        v = [x for t in rows.values() for x in t.get(c, [])]
        if v: print(f"  {c:12s} runs {len(v):4d}  success {sum(v)/len(v):.3f}  tasks-any {sum(any(t.get(c, [])) for t in rows.values())/len(rows):.3f}")
    # paired enhanced vs original per task (mean over resamples), bootstrap CI
    import random
    pairs = [(sum(t["enhanced"]) / len(t["enhanced"]), sum(t["original"]) / len(t["original"]))
             for t in rows.values() if t.get("enhanced") and t.get("original")]
    if pairs:
        d = [e - o for e, o in pairs]; mean = sum(d) / len(d)
        rng = random.Random(0); bs = []
        for _ in range(2000):
            s = [d[rng.randrange(len(d))] for _ in d]; bs.append(sum(s) / len(s))
        bs.sort()
        print(f"  enhanced - original: {mean:+.3f}  95% CI [{bs[50]:+.3f}, {bs[1949]:+.3f}]  (n={len(d)} tasks)")
    oc = [json.load(open(p)) for p in glob.glob(os.path.join(TRACES, "inj", "*", "oracle.json"))]
    if oc:
        kept = sum(o.get("n_kept", 0) for o in oc); tot = sum(o.get("n_total", 0) for o in oc)
        print(f"  oracle: {len(oc)} calls, i distribution {dict(Counter(o.get('i') for o in oc))}, grounding kept {kept}/{tot}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--inj", action="store_true"); ap.add_argument("--arms", default="relay,ceiling")
    a = ap.parse_args()
    if a.inj: summarize_inj()
    else: summarize_arms(a.arms.split(","))
