"""Summarize the two-atom internal-belief arms (int2_*).

  python lip/internal/summarize_2atom.py
Per arm: runs, accuracy, finished_by; paired bootstrap over tasks for the planned comparisons. If atom_judge.py has run:
per arm, how often the final follows the EARLY atom (first_atom: agent 1's in the split arms) and the LATE atom, the
reading distribution, and "stated but unheeded" (atom conveyed in the finisher's incoming handoff, final does not follow it).
"""
import glob, json, os, random, sys
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
TRACES = os.path.join(HERE, "..", "traces")
TASKS = os.path.join(HERE, "..", "data", "tasks_internal_2atom.jsonl")
ARMS = ["int2_none", "int2_both1", "int2_split13", "int2_all", "int2_split35", "int2_all5"]   # last two: only agent 5 may finish
PAIRS = [("int2_both1", "int2_none"), ("int2_split13", "int2_both1"), ("int2_all", "int2_both1"),
         ("int2_all", "int2_split13"), ("int2_split13", "int2_none"), ("int2_split35", "int2_all5"), ("int2_all5", "int2_all"),
         ("int2_split35", "int2_split13")]

def load(arm):
    R = defaultdict(list)
    for p in glob.glob(os.path.join(TRACES, arm, "*", "run_*", "run.json")):
        tr = json.load(open(p))
        if not tr.get("error") and tr.get("agents"): R[tr["task_id"]].append(tr)
    return R

def boot(R1, R2, n=5000):
    ts = sorted(set(R1) & set(R2))
    if not ts: return None
    d = [sum(bool(r["correct"]) for r in R1[t]) / len(R1[t]) - sum(bool(r["correct"]) for r in R2[t]) / len(R2[t]) for t in ts]
    rng = random.Random(0); m = sum(d) / len(d)
    bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
    return m, bs[int(.025 * n)], bs[int(.975 * n)], len(ts)

def main():
    R = {a: load(a) for a in ARMS if os.path.isdir(os.path.join(TRACES, a))}
    print(f"{'arm':16} {'tasks':>5} {'runs':>5} {'acc':>6}  finished_by")
    for a, V in R.items():
        rs = [r for v in V.values() for r in v]
        print(f"{a:16} {len(V):5} {len(rs):5} {sum(bool(r['correct']) for r in rs)/max(1,len(rs)):6.3f}  "
              f"{dict(sorted(Counter(r.get('finished_by') for r in rs).items(), key=lambda x: str(x[0])))}")
    print("\npaired bootstrap over tasks (per-task mean accuracy, 5000 resamples):")
    for x, y in PAIRS:
        if x in R and y in R and (b := boot(R[x], R[y])):
            print(f"  {x[5:]:>10} - {y[5:]:<10} {b[0]:+.3f} [{b[1]:+.3f}, {b[2]:+.3f}]  n={b[3]}")
    judged = {a: [r for v in V.values() for r in v if r.get("atom_judge")] for a, V in R.items()}
    if not any(judged.values()): return
    print("\nper-atom (atom_judge): final follows EARLY atom (first_atom) / LATE atom; reading distribution")
    for a, rs in judged.items():
        if not rs: continue
        def fol(r, which):
            k = r["first_atom"] if which == "early" else ("B" if r["first_atom"] == "A" else "A")
            return (r["atom_judge"].get(k) or {}).get("final")
        e = Counter(fol(r, "early") for r in rs); l = Counter(fol(r, "late") for r in rs)
        rd = Counter()
        for r in rs:   # reading relabelled early/late
            x = r["atom_judge"].get("reading"); fa = r["first_atom"]
            rd[{"both": "both", "neither": "neither", f"{fa}_only": "early_only"}.get(x, "late_only" if x in ("A_only", "B_only") else "other")] += 1
        print(f"  {a:16} n={len(rs):4}  early yes {e['yes']/len(rs):.2f}  late yes {l['yes']/len(rs):.2f}  readings {dict(rd.most_common())}")
    print("\nstated but unheeded: atom conveyed in the finisher's incoming handoff, final does not follow it (runs finished by agent >= 2)")
    for a, rs in judged.items():
        n_st = n_un = 0
        for r in rs:
            fb = r.get("finished_by") or 0
            for k in ("A", "B"):
                j = r["atom_judge"].get(k) or {}
                if (fb - 1) in (j.get("handoffs") or []):
                    n_st += 1; n_un += j.get("final") == "no"
        if n_st: print(f"  {a:16} atom stated in last handoff {n_st:4}, unheeded {n_un:4} ({n_un/n_st:.2f})")

if __name__ == "__main__":
    main()
