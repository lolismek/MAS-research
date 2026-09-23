"""Fixed-total-budget N sweep (N*K = 16): accuracy vs N, paired by task, and where information is lost.

  python lip/metrics/sweep.py [--plot lip/results/sweep/acc_vs_n.png]

Arms: ceiling (1x16), relay_2x8, relay_4x4, relay (8x2), relay_16x1. Per arm: run accuracy with a task-level bootstrap
CI, paired difference vs the ceiling, finished_by (how many handoffs a run actually crossed), invalid handoffs, and the
mechanical found-but-lost rate (gold page seen by agent j, absent from agent j's handoff) overall and by agent position.
"""
import argparse, json, os, random, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from summarize import load_runs, gold_title_map, url_to_title, found_but_lost, DATA

ARMS = [("ceiling", 1, 16), ("relay_2x8", 2, 8), ("relay_4x4", 4, 4), ("relay", 8, 2), ("relay_16x1", 16, 1)]
B = 2000

def task_acc(runs):
    by = defaultdict(list)
    for r in runs: by[r["task_id"]].append(bool(r["correct"]))
    return {t: sum(v) / len(v) for t, v in by.items()}

def boot(vals, rng):
    vals = list(vals); m = sum(vals) / len(vals); bs = []
    for _ in range(B):
        s = [vals[rng.randrange(len(vals))] for _ in vals]; bs.append(sum(s) / len(s))
    bs.sort(); return m, bs[int(0.025 * B)], bs[int(0.975 * B) - 1]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--plot", default=None); a = ap.parse_args()
    tasks = {t["id"]: t for t in (json.loads(l) for l in open(os.path.join(DATA, "tasks.jsonl")))}
    gmap = gold_title_map(); rng = random.Random(0)
    runs = {arm: [r for r in load_runs(arm) if not r.get("error")] for arm, _, _ in ARMS}
    accs = {arm: task_acc(v) for arm, v in runs.items() if v}
    common = set.intersection(*(set(v) for v in accs.values())) if accs else set()
    judges = {arm: sorted({(r.get("score") or {}).get("model") or ("em" if (r.get("score") or {}).get("em") else "empty-answer")
                           for r in v}) for arm, v in runs.items()}
    print(f"tasks with runs in every arm: {len(common)}")
    rows = []
    for arm, N, K in ARMS:
        v = runs[arm]
        if not v: print(f"{arm:11s} no runs"); continue
        ta = accs[arm]; m, lo, hi = boot([ta[t] for t in common], rng)
        d = [ta[t] - accs["ceiling"][t] for t in common] if "ceiling" in accs else []
        dm, dlo, dhi = boot(d, rng) if d and arm != "ceiling" else (0, 0, 0)
        fin = defaultdict(int)
        for r in v: fin[r.get("finished_by")] += 1
        crossed = sum((r.get("finished_by") or N) - 1 for r in v) / len(v)
        inv = sum(a.get("handoff_invalid", False) for r in v for a in r["agents"]) / max(1, sum(r["agents"][-1]["agent"] - 1 for r in v))
        # found-but-lost by agent position
        seen_pos = defaultdict(int); lost_pos = defaultdict(int)
        for r in v:
            t = tasks.get(r["task_id"])
            if not t: continue
            gts = [gmap.get(g, g) for g in t.get("gold_titles") or [url_to_title(u) for u in t["gold_links"]]]
            for x in found_but_lost(r, gts):
                for j in x["seen_by"]:
                    ag = r["agents"][j - 1]
                    if ag["handoff"] is None: continue          # agent finished: nothing handed on
                    seen_pos[j] += 1; lost_pos[j] += j in x["lost_at"]
        S = sum(seen_pos.values()); Lz = sum(lost_pos.values())
        rows.append((arm, N, K, m, lo, hi))
        print(f"{arm:11s} {N:2d}x{K:<2d} n={len(v):3d} acc {m:.3f} [{lo:.3f},{hi:.3f}] | vs ceiling {dm:+.3f} [{dlo:+.3f},{dhi:+.3f}] "
              f"| handoffs crossed/run {crossed:.2f} | invalid handoff rate {inv:.3f} | seen-then-dropped {Lz}/{S}={Lz/max(1,S):.2f} | judge {judges[arm]}")
        if N > 1:
            print("            finished_by " + " ".join(f"a{k}:{fin[k]}" for k in sorted(fin, key=lambda x: (x is None, x))))
            print("            dropped@agent " + " ".join(f"a{j}:{lost_pos[j]}/{seen_pos[j]}" for j in sorted(seen_pos)))
    if a.plot and rows:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        os.makedirs(os.path.dirname(a.plot), exist_ok=True)
        xs = [r[1] for r in rows]; ys = [r[3] for r in rows]
        err = [[r[3] - r[4] for r in rows], [r[5] - r[3] for r in rows]]
        fig, ax = plt.subplots(figsize=(4.5, 3.2))
        ax.errorbar(xs, ys, yerr=err, marker="o", capsize=3)
        ax.set_xscale("log", base=2); ax.set_xticks(xs); ax.set_xticklabels([f"{r[1]}x{r[2]}" for r in rows])
        ax.set_xlabel("agents x tool calls each (total 16)"); ax.set_ylabel("accuracy (FRAMES, 155 tasks)")
        fig.tight_layout(); fig.savefig(a.plot, dpi=200); print("plot ->", a.plot)

if __name__ == "__main__":
    main()
