"""Table-1 summary for one benchmark: single agent vs relay accuracy (task-bootstrap CIs), mechanical found-but-lost,
and the oracle-patching result (paired gain, loss score, fact/note split, per-edge incl. full-length runs).

  LIP_BENCH=fanoutqa python lip/metrics/bench_summary.py --ceiling foqa_ceiling --relay foqa_relay --inj foqa_inj
"""
import argparse, glob, json, os, random, re, sys
from collections import defaultdict, Counter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
sys.path.insert(0, os.path.dirname(__file__))
from bench import CFG
from summarize import found_but_lost, load_runs

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRACES = os.path.join(ROOT, "lip", "traces")

def boot(d, n=5000, seed=0):
    rng = random.Random(seed); m = sum(d) / len(d); bs = []
    for _ in range(n):
        s = [d[rng.randrange(len(d))] for _ in d]; bs.append(sum(s) / len(s))
    bs.sort(); return m, bs[int(0.025 * n)], bs[int(0.975 * n) - 1]

def gold_map():
    """requested title -> resolved page title, from the corpus gold records (redirects)."""
    m = {}
    for fn in glob.glob(os.path.join(CFG["corpus"], "gold", "*.json")):
        r = json.load(open(fn))
        if not r.get("missing"): m[r["requested"]] = r["title"]
    return m

def per_task_acc(arm):
    by = defaultdict(list)
    for r in load_runs(arm):
        if r.get("error") is None and r.get("correct") is not None: by[r["task_id"]].append(bool(r["correct"]))
    return {t: sum(v) / len(v) for t, v in by.items()}, by

def arms(ceiling, relay, tasks):
    ca, cb = per_task_acc(ceiling); ra, rb = per_task_acc(relay)
    common = sorted(set(ca) & set(ra))
    for name, a, b in ((ceiling, ca, cb), (relay, ra, rb)):
        m, lo, hi = boot([a[t] for t in common])
        print(f"{name:16s} acc {m:.3f} [{lo:.3f},{hi:.3f}]  runs {sum(len(b[t]) for t in common)}  tasks {len(common)}")
    m, lo, hi = boot([ra[t] - ca[t] for t in common])
    print(f"relay - single    {m:+.3f} [{lo:+.3f},{hi:+.3f}]")
    gm = gold_map(); n = seen = lost = 0
    for r in load_runs(relay):
        if r.get("error") or r["task_id"] not in tasks: continue
        for x in found_but_lost(r, [gm.get(g, g) for g in tasks[r["task_id"]]["gold_titles"]]):
            n += 1; seen += bool(x["seen_by"]); lost += bool(x["lost_at"])
    if n: print(f"relay gold pages {n}: seen {seen/n:.2f}, seen-then-absent-from-handoff {lost/n:.2f}")
    fb = Counter(r.get("finished_by") for r in load_runs(relay) if not r.get("error"))
    print(f"relay finished_by {dict(sorted(fb.items()))}")
    return 1 - sum(ra[t] for t in common) / len(common)

def inj(out, relay, p_fail):
    rows = defaultdict(dict)
    for p in glob.glob(os.path.join(TRACES, out, "*", "*", "run_*", "run.json")):
        r = json.load(open(p))
        if r.get("error") or r.get("correct") is None: continue
        rows[r["task_id"]].setdefault(r["condition"], []).append(bool(r["correct"]))
    pairs = {t: (sum(v["enhanced"]) / len(v["enhanced"]), sum(v["original"]) / len(v["original"]))
             for t, v in rows.items() if v.get("enhanced") and v.get("original")}
    if not pairs: print("no injection results"); return
    oc = {os.path.basename(os.path.dirname(p)): json.load(open(p)) for p in glob.glob(os.path.join(TRACES, out, "*", "oracle.json"))}
    d = [e - o for e, o in pairs.values()]; m, lo, hi = boot(d)
    print(f"\npatching: {len(oc)} oracle calls, {sum(bool(o.get('declined')) for o in oc.values())} declined, {len(pairs)} patched")
    print(f"  original {sum(o for _, o in pairs.values())/len(pairs):.3f}  patched {sum(e for e, _ in pairs.values())/len(pairs):.3f}")
    print(f"  gain {m:+.3f} [{lo:+.3f},{hi:+.3f}]  wins {sum(x > 0 for x in d)} losses {sum(x < 0 for x in d)}")
    print(f"  loss score L = P(fail) {p_fail:.3f} x gain {m:+.3f} = {p_fail * m:.3f}")
    kept = sum(o.get("n_kept", 0) for o in oc.values()); tot = sum(o.get("n_total", 0) for o in oc.values())
    print(f"  grounding kept {kept}/{tot}")
    has_fact = {t for t in pairs if any(a.get("kept") and a.get("kind") == "fact" for a in oc[t].get("addendum", []))}
    fact = [e - o for t, (e, o) in pairs.items() if t in has_fact]
    note = [e - o for t, (e, o) in pairs.items() if t not in has_fact]
    for name, v in (("with >=1 fact", fact), ("notes only", note)):
        if v: print(f"  {name}: n={len(v)} gain {sum(v)/len(v):+.3f}")
    # edges, and within runs that reached agent N
    by_i = defaultdict(list); full = defaultdict(list); into_last = 0; forced2 = 0
    for t, (e, o) in pairs.items():
        i = int(oc[t]["i"]); src = json.load(open(os.path.join(TRACES, relay, t, f"run_{oc[t]['source_run']}", "run.json")))
        L = len(src["agents"]); by_i[i].append(e - o); into_last += (i == L); forced2 += (i == 2 and L == 2)
        if L == src["N"]: full["late" if i >= src["N"] - 2 else "early"].append(e - o)
    print("  by edge: " + ", ".join(f"{i}: {sum(v)/len(v):+.2f} ({len(v)})" for i, v in sorted(by_i.items())))
    print(f"  patched into the answering agent {into_last}/{len(pairs)}; edge-2 patches from runs that ended at agent 2: {forced2}/{len(by_i.get(2, []))}")
    for k in ("early", "late"):
        if full[k]: print(f"  full-length runs, {k} edges: n={len(full[k])} gain {sum(full[k])/len(full[k]):+.3f}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ceiling", required=True); ap.add_argument("--relay", required=True); ap.add_argument("--inj")
    a = ap.parse_args()
    tasks = {t["id"]: t for t in (json.loads(l) for l in open(CFG["tasks"]))}
    p_fail = arms(a.ceiling, a.relay, tasks)
    if a.inj: inj(a.inj, a.relay, p_fail)
