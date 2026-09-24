"""Oracle patching across N (fixed budget N*K = 16): loss score L(N), paired gain, and where the patch helps.

  python lip/metrics/inj_sweep.py [--tasks lip/data/tasks_injN50.jsonl] [--plot lip/results/inj_sweep/loss_vs_n.png]
--tasks: the task set L is averaged over (default: all 155 screened; tasks_injN<n>.jsonl = first n of a seed-0 shuffle)

Per task t of the 155 screened tasks, with source arm runs r (3 per task):
  w(t)  = share of t's source runs that failed AND crossed at least one handoff (only those can be patched)
  d(t)  = mean(enhanced) - mean(original) over the M resamples of the patched suffix, or 0 when there is nothing to
          patch (no such failed run, oracle declined, or every addendum sentence failed grounding)
  L(N)  = mean_t w(t) * d(t)          (expected accuracy one oracle addition recovers per run; L(1) = 0)
Task-level bootstrap CIs (B=2000). Also: paired gain on patched tasks (the N=8 paper number), declines, gain by edge.
"""
import argparse, glob, json, os, random, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from summarize import load_runs, TRACES, DATA

ARMS = [("relay_2x8", "injN_2x8", 2, 8), ("relay_4x4", "injN_4x4", 4, 4), ("relay", "injN_8x2", 8, 2),
        ("relay_16x1", "injN_16x1", 16, 1)]
REF = ("relay", "inj", 8, 2)     # 2026-09-14 batch, gpt-5.5 oracle: reference row only
B = 2000

def boot(vals, rng):
    vals = list(vals)
    if not vals: return float("nan"), float("nan"), float("nan")
    m = sum(vals) / len(vals); bs = []
    for _ in range(B):
        s = [vals[rng.randrange(len(vals))] for _ in vals]; bs.append(sum(s) / len(s))
    bs.sort(); return m, bs[int(0.025 * B)], bs[int(0.975 * B) - 1]

def patched(inj):
    """{task: dict(i, enhanced=[bool], original=[bool], kinds)} for tasks whose suffix ran under both conditions."""
    out = {}
    for d in glob.glob(os.path.join(TRACES, inj, "*")):
        t = os.path.basename(d); o = os.path.join(d, "oracle.json")
        if not os.path.exists(o): continue
        oo = json.load(open(o)); rec = dict(i=oo.get("i"), declined=bool(oo.get("declined")), n_kept=oo.get("n_kept", 0),
                                          kinds={a.get("kind") for a in oo.get("addendum", []) if a.get("kept")})
        for c in ("enhanced", "original"):
            rec[c] = [json.load(open(p)).get("correct") for p in sorted(glob.glob(os.path.join(d, c, "run_*", "run.json")))]
            rec[c] = [bool(x) for x in rec[c] if x is not None]
        out[t] = rec
    return out

def arm_stats(src, inj, N, tasks, rng):
    runs = defaultdict(list)
    for r in load_runs(src):
        if not r.get("error"): runs[r["task_id"]].append(r)
    P = patched(inj)
    w, dd, gains, by_edge = {}, {}, [], defaultdict(list)
    for t in tasks:
        rs = runs.get(t, [])
        w[t] = sum(1 for r in rs if r.get("correct") is False and len(r["agents"]) >= 2) / len(rs) if rs else 0.0
        p = P.get(t)
        if p and p["enhanced"] and p["original"] and p["n_kept"]:
            dd[t] = sum(p["enhanced"]) / len(p["enhanced"]) - sum(p["original"]) / len(p["original"])
            gains.append((t, dd[t], p)); by_edge[p["i"]].append(dd[t])
        else: dd[t] = 0.0
    L = boot([w[t] * dd[t] for t in tasks], rng)
    G = boot([g for _, g, _ in gains], rng)
    enh = [x for _, _, p in gains for x in p["enhanced"]]; org = [x for _, _, p in gains for x in p["original"]]
    fact = [g for _, g, p in gains if "fact" in p["kinds"]]; note = [g for _, g, p in gains if p["kinds"] == {"note"}]
    eligible = sum(1 for t in tasks if w[t] > 0)
    oracled = [p for t, p in P.items() if t in tasks]
    return dict(N=N, L=L, G=G, n=len(gains), eligible=eligible, oracled=len(oracled),
                declined=sum(p["declined"] for p in oracled), empty=sum(1 for p in oracled if not p["declined"] and not p["n_kept"]),
                acc_enh=sum(enh) / max(1, len(enh)), acc_org=sum(org) / max(1, len(org)), up=sum(g > 0 for _, g, _ in gains),
                down=sum(g < 0 for _, g, _ in gains), fact=boot(fact, rng)[0] if fact else None, note=boot(note, rng)[0] if note else None,
                n_fact=len(fact), n_note=len(note), by_edge={i: (sum(v) / len(v), len(v)) for i, v in sorted(by_edge.items(), key=lambda x: (x[0] is None, x[0]))},
                mean_w=sum(w.values()) / len(tasks))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--plot", default=None)
    ap.add_argument("--tasks", default=os.path.join(DATA, "tasks_screened.jsonl")); a = ap.parse_args()
    tasks = [json.loads(l)["id"] for l in open(a.tasks)]
    rng = random.Random(0); rows = []
    print(f"{len(tasks)} tasks; L = mean_t w(t)*d(t), w = share of runs failed after >=1 handoff\n")
    for src, inj, N, K in ARMS + [REF]:
        if not os.path.isdir(os.path.join(TRACES, inj)): print(f"{inj}: no traces"); continue
        s = arm_stats(src, inj, N, tasks, rng)
        lab = f"{N}x{K}" + (" (gpt-5.5 oracle, ref)" if inj == "inj" else "")
        print(f"{lab:26s} L {s['L'][0]:+.4f} [{s['L'][1]:+.4f},{s['L'][2]:+.4f}] | mean w {s['mean_w']:.3f} | "
              f"eligible {s['eligible']} oracle {s['oracled']} declined {s['declined']} empty-after-grounding {s['empty']} patched {s['n']}")
        print(f"{'':26s} paired gain on patched {s['G'][0]:+.3f} [{s['G'][1]:+.3f},{s['G'][2]:+.3f}] "
              f"(orig {s['acc_org']:.3f} -> enh {s['acc_enh']:.3f}; up {s['up']} down {s['down']}) | "
              f"with fact {s['fact'] if s['fact'] is None else round(s['fact'], 3)} (n={s['n_fact']}) notes-only "
              f"{s['note'] if s['note'] is None else round(s['note'], 3)} (n={s['n_note']})")
        print(f"{'':26s} gain by edge i: " + " ".join(f"i{i}:{g:+.2f}({n})" for i, (g, n) in s["by_edge"].items()))
        if inj != "inj": rows.append(s)
    if a.plot and rows:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        os.makedirs(os.path.dirname(a.plot), exist_ok=True)
        xs = [1] + [r["N"] for r in rows]; ys = [0] + [r["L"][0] for r in rows]
        err = [[0] + [r["L"][0] - r["L"][1] for r in rows], [0] + [r["L"][2] - r["L"][0] for r in rows]]
        fig, ax = plt.subplots(figsize=(4.5, 3.2))
        ax.errorbar(xs, ys, yerr=err, marker="o", capsize=3); ax.axhline(0, color="grey", lw=0.5)
        ax.set_xscale("log", base=2); ax.set_xticks(xs); ax.set_xticklabels([f"{n}x{16 // n}" for n in xs])
        ax.set_xlabel("agents x tool calls each (total 16)"); ax.set_ylabel("loss score L")
        fig.tight_layout(); fig.savefig(a.plot, dpi=200); print("plot ->", a.plot)

if __name__ == "__main__":
    main()
