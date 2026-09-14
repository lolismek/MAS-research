"""Summarize the internal-belief arms.

  python lip/internal/summarize.py                # arms internal_none / internal_first / internal_all (+ internal_last if present)
Per arm: runs, accuracy, finished_by distribution. Plus:
  - default-reading rate: among internal_first failures, share whose final equals the modal internal_none final
    for that task (the interpretation was lost, not the capability);
  - externalization at edge 1: share of internal_first runs where agent 1's handoff carries the qualifier
    (>= half of the qualifier's content tokens, or any 4-digit year in it).
"""
import json, os, re, sys, glob
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
from judge import normalize
TRACES = os.path.join(HERE, "..", "traces")
TASKS = os.path.join(HERE, "..", "data", "tasks_internal.jsonl")
STOP = set("the a an of in on at as by for to and or is was were be with from that this which who whom it its".split())

def load(arm):
    runs = defaultdict(list)
    for p in glob.glob(os.path.join(TRACES, arm, "*", "run_*", "run.json")):
        tr = json.load(open(p))
        if tr.get("error"): continue
        runs[tr["task_id"]].append(tr)
    return runs

def qual_tokens(q):
    return [w for w in re.findall(r"[a-z0-9]+", (q or "").lower()) if w not in STOP]

def carries(handoff, qualifier):
    h = (handoff or "").lower(); toks = qual_tokens(qualifier)
    if not toks: return False
    years = re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", qualifier or "")
    if years and any(y in h for y in years): return True
    return sum(t in h for t in toks) >= max(1, (len(toks) + 1) // 2)

def main():
    tasks = {t["id"]: t for t in (json.loads(l) for l in open(TASKS))} if os.path.exists(TASKS) else {}
    arms = [a for a in ("internal_none", "internal_first", "internal_last", "internal_all") if os.path.isdir(os.path.join(TRACES, a))]
    R = {a: load(a) for a in arms}
    print(f"{'arm':16} {'tasks':>5} {'runs':>5} {'acc':>6}  finished_by")
    for a in arms:
        rs = [r for v in R[a].values() for r in v]
        acc = sum(bool(r.get("correct")) for r in rs) / max(1, len(rs))
        fb = Counter(r.get("finished_by") for r in rs)
        print(f"{a:16} {len(R[a]):5} {len(rs):5} {acc:6.3f}  {dict(sorted(fb.items(), key=lambda x: str(x[0])))}")
    common = set.intersection(*(set(R[a]) for a in arms)) if arms else set()
    if len(arms) > 1 and common:
        print(f"\npaired on {len(common)} tasks present in every arm (per-task mean accuracy):")
        for a in arms:
            m = sum(sum(bool(r.get('correct')) for r in R[a][t]) / len(R[a][t]) for t in common) / len(common)
            print(f"  {a:16} {m:.3f}")
    if "internal_first" in R and "internal_none" in R:
        modal = {t: Counter(normalize(r.get("final") or "") for r in v).most_common(1)[0][0] for t, v in R["internal_none"].items()}
        fails = [r for v in R["internal_first"].values() for r in v if not r.get("correct")]
        lost = [r for r in fails if modal.get(r["task_id"]) and normalize(r.get("final") or "") == modal[r["task_id"]]]
        print(f"\ninternal_first failures: {len(fails)}; final == modal no-belief answer (interpretation lost): {len(lost)}")
    if "internal_first" in R and tasks:
        rs = [r for v in R["internal_first"].values() for r in v if r["agents"] and r["agents"][0].get("handoff") is not None]
        ext = [carries(r["agents"][0]["handoff"], tasks.get(r["task_id"], {}).get("qualifier")) for r in rs]
        print(f"edge-1 externalization (agent 1 handoff carries the qualifier): {sum(ext)}/{len(ext)}"
              f"  [{len([r for v in R['internal_first'].values() for r in v]) - len(rs)} runs finished by agent 1, excluded]")
        byq = defaultdict(list)
        for r, e in zip(rs, ext): byq[tasks.get(r["task_id"], {}).get("qualifier_type")].append(e)
        print("  by qualifier type:", {k: f"{sum(v)}/{len(v)}" for k, v in byq.items()})

if __name__ == "__main__":
    main()
