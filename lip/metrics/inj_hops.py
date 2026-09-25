"""Oracle patching across N: paired gain by the number of handoffs left after the patched edge, and the paper figure.

  python lip/metrics/inj_hops.py [--fig ~/Desktop/lip-paper/figures/loss_vs_n.pdf]

Handoffs left after a patch at edge i of an N-agent relay = N - i (0: the patched agent is the last one).
Left panel: loss score L(N) (inj_sweep.arm_stats, all 155 screened tasks). Right panel: paired gain by handoffs left,
Qwen3.5-397B oracle pooled over 2x8 / 8x2 / 16x1, and the gpt-5.5 oracle at 8x2.
"""
import argparse, json, os, random, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from inj_sweep import patched, boot, arm_stats, ARMS
from summarize import DATA

BUCKETS = [(0, 0, "0"), (1, 2, "1-2"), (3, 5, "3-5"), (6, 99, "6+")]
QWEN = [("injN_2x8", 2), ("injN_8x2", 8), ("injN_16x1", 16)]
GPT = [("inj", 8)]

def by_hops(arms, rng):
    b = defaultdict(list)
    for inj, N in arms:
        for t, p in patched(inj).items():
            if not (p["enhanced"] and p["original"] and p["n_kept"]): continue
            d = sum(p["enhanced"]) / len(p["enhanced"]) - sum(p["original"]) / len(p["original"])
            h = N - p["i"]
            b[next(lab for lo, hi, lab in BUCKETS if lo <= h <= hi)].append(d)
    return {lab: (*boot(b[lab], rng), len(b[lab])) for _, _, lab in BUCKETS if b[lab]}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fig", default=None)
    ap.add_argument("--skip", default="4x4", help="arms left out of the L(N) panel (incomplete)"); a = ap.parse_args()
    rng = random.Random(0)
    q, g = by_hops(QWEN, rng), by_hops(GPT, rng)
    print("handoffs left -> paired gain [95% CI] (n)")
    for _, _, lab in BUCKETS:
        row = [f"{lab:4s}"]
        for name, d in (("qwen", q), ("gpt-5.5 8x2", g)):
            if lab in d: m, lo, hi, n = d[lab]; row.append(f"{name} {m:+.3f} [{lo:+.3f},{hi:+.3f}] (n={n})")
        print("  " + " | ".join(row))
    if not a.fig: return
    tasks = [json.loads(l)["id"] for l in open(os.path.join(DATA, "tasks_screened.jsonl"))]
    rows = [arm_stats(src, inj, N, tasks, rng) for src, inj, N, K in ARMS if f"{N}x{K}" not in a.skip.split(",")]
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 2.9))
    xs = [1] + [r["N"] for r in rows]; ys = [0] + [r["L"][0] for r in rows]
    err = [[0] + [r["L"][0] - r["L"][1] for r in rows], [0] + [r["L"][2] - r["L"][0] for r in rows]]
    ax1.errorbar(xs, ys, yerr=err, marker="o", capsize=3, color="C0"); ax1.axhline(0, color="grey", lw=0.5)
    ax1.set_xscale("log", base=2); ax1.set_xticks([1, 2, 4, 8, 16]); ax1.set_xticklabels(["1", "2", "4", "8", "16"])
    ax1.set_xlabel("number of agents $N$ ($N \\cdot K = 16$)"); ax1.set_ylabel("loss score $\\mathcal{L}$")
    labs = [lab for _, _, lab in BUCKETS]; x = range(len(labs)); w = 0.38
    for off, d, name, c in ((-w / 2, q, "Qwen3.5-397B oracle, $N \\in \\{2,8,16\\}$", "C0"), (w / 2, g, "GPT-5.5 oracle, $N = 8$", "C1")):
        m = [d[l][0] if l in d else 0 for l in labs]
        e = [[d[l][0] - d[l][1] if l in d else 0 for l in labs], [d[l][2] - d[l][0] if l in d else 0 for l in labs]]
        ax2.bar([i + off for i in x], m, w, yerr=e, capsize=2, color=c, label=name, error_kw=dict(lw=0.8))
        for i, l in enumerate(labs):
            if l in d: ax2.text(i + off, -0.13, f"{d[l][3]}", ha="center", fontsize=6, color=c)
    ax2.axhline(0, color="grey", lw=0.5); ax2.set_xticks(list(x)); ax2.set_xticklabels(labs)
    ax2.set_xlabel("handoffs left after the patched edge"); ax2.set_ylabel("paired gain"); ax2.set_ylim(-0.15, 0.5)
    ax2.legend(fontsize=6.5, frameon=False, loc="upper right")
    fig.tight_layout(); os.makedirs(os.path.dirname(os.path.expanduser(a.fig)), exist_ok=True)
    fig.savefig(os.path.expanduser(a.fig)); print("fig ->", a.fig)

if __name__ == "__main__":
    main()
