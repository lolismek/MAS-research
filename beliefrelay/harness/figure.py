"""Two-panel results figure: accuracy per arm (Wilson 95% CI) for the MATH-L5
capped relay (v2) and the FEVER two-way relay (v3).

  conda run -n base python beliefrelay/harness/figure.py [outpath]
"""
import json
import math
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARMS = ["none", "homo", "probe"]
LABELS = {"none": "none\n(filler)", "homo": "homo\n(shared beliefs)",
          "probe": "probe\n(different beliefs)"}
COLORS = {"none": "#9aa5b1", "homo": "#4c78a8", "probe": "#e45756"}


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def arm_stats(path):
    agg = defaultdict(lambda: [0, 0])
    for line in open(os.path.join(ROOT, "results", path)):
        r = json.loads(line)
        agg[r["arm"]][0] += r["correct"]
        agg[r["arm"]][1] += 1
    return {a: wilson(*agg[a]) for a in ARMS}


def panel(ax, stats, title, subtitle):
    xs = range(len(ARMS))
    for x, a in zip(xs, ARMS):
        p, lo, hi = stats[a]
        ax.bar(x, p, 0.62, color=COLORS[a], zorder=3)
        ax.errorbar(x, p, yerr=[[p - lo], [hi - p]], fmt="none", ecolor="#222",
                    capsize=5, lw=1.4, zorder=4)
        ax.text(x, p + (hi - p) + 0.025, f"{p*100:.1f}%", ha="center",
                fontsize=11, fontweight="bold")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([LABELS[a] for a in ARMS], fontsize=10)
    ax.set_ylim(0, 1.09)
    ax.set_title(f"{title}\n{subtitle}", fontsize=11)
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        "~/Desktop/beliefrelay_results.png")
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.4), sharey=True,
                             gridspec_kw=dict(wspace=0.12))
    panel(axes[0], arm_stats("grid_v2.jsonl"),
          "MATH-L5 — capped handoff relay (v2)",
          "39 tasks × k=3, cap 4500 — deltas ns")
    panel(axes[1], arm_stats("grid_fever.jsonl"),
          "FEVER two-way — directional beliefs (v3)",
          "24 claims × k=2, cap 2500 — ns; shift 0.000")
    axes[0].set_ylabel("accuracy (Wilson 95% CI)", fontsize=11)
    fig.suptitle("beliefrelay: belief injection in a 3-agent relay — "
                 "accuracy per arm", fontsize=13, y=1.0)
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
