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


def panel(ax, stats, title, subtitle, ylo, yhi):
    xs = range(len(ARMS))
    span = yhi - ylo
    for x, a in zip(xs, ARMS):
        p = stats[a][0]
        ax.bar(x, p - ylo, 0.62, bottom=ylo, color=COLORS[a], zorder=3)
        ax.text(x, p + span * 0.03, f"{p*100:.1f}%", ha="center",
                fontsize=11, fontweight="bold")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([LABELS[a] for a in ARMS], fontsize=10)
    ax.set_ylim(ylo, yhi)
    ax.set_title(f"{title}\n{subtitle}", fontsize=11)
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        "~/Desktop/beliefrelay_results.png")
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.4),
                             gridspec_kw=dict(wspace=0.18))
    panel(axes[0], arm_stats("grid_v2.jsonl"),
          "MATH-L5",
          "39 tasks × k=3, cap 4500 — deltas ns", 0.5, 0.8)
    panel(axes[1], arm_stats("grid_fever.jsonl"),
          "FEVER",
          "24 claims × k=2, cap 2500 — ns; shift 0.000", 0.8, 1.0)
    axes[0].set_ylabel("accuracy", fontsize=11)
    fig.suptitle("beliefrelay: belief injection in a 3-agent relay — "
                 "accuracy per arm", fontsize=14, fontweight="bold", y=0.97)
    fig.subplots_adjust(top=0.76, bottom=0.14, left=0.08, right=0.97,
                        wspace=0.22)
    fig.savefig(out, dpi=200)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
