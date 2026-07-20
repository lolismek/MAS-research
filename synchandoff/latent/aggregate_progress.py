"""Incremental latent-wave aggregation -> results/latent_progress.txt.

Runs pilot_report.py's tables (latent conditions appear via runs/ naming)
plus per-latent-arm episode timing derived from result.json mtimes (arm span
x lanes / n -> approximate mean episode wall time; good enough to plan the
A-solved pass). Run on piranha from /tmp/aij2115/synchandoff:
  /tmp/aij2115/pyenv/bin/python latent/aggregate_progress.py
"""
import io
import json
import os
import sys
import time
from collections import defaultdict
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import pilot_report as PR  # noqa: E402

LATENT_CONDS = ["lkv", "lkv_notekv", "lkv_rand", "lthought", "lthought_rand",
                "lthought_pool", "lprobe", "lprobe_shuffled"]
LANES = 4


def timing_table(runs_dir):
    stamps = defaultdict(list)
    for root, _, files in os.walk(runs_dir):
        if "result.json" not in files:
            continue
        cond = os.path.basename(root).split("_k12")[0]
        if cond in LATENT_CONDS:
            stamps[cond].append(os.path.getmtime(os.path.join(root, "result.json")))
    lines = ["=== latent per-arm episode timing (approx: span x lanes / n)"]
    lines.append(f"{'condition':>15} {'n':>3} {'span_min':>9} {'est_min/episode':>16}")
    for cond in LATENT_CONDS:
        ts = sorted(stamps.get(cond, []))
        if not ts:
            continue
        span = (ts[-1] - ts[0]) / 60
        est = span * LANES / len(ts) if len(ts) > 1 else float("nan")
        lines.append(f"{cond:>15} {len(ts):>3} {span:>9.1f} {est:>16.1f}")
    return "\n".join(lines)


def main():
    frozen = os.path.join(ROOT, "phase1_frozen")
    runs = os.path.join(ROOT, "runs")
    buf = io.StringIO()
    with redirect_stdout(buf):
        metas = PR.load_metas(frozen)
        rr = PR.load_runs(runs)
        PR.g2_table(rr, metas)
    out = [f"latent wave progress @ {time.strftime('%Y-%m-%d %H:%M:%S')}",
           f"(runs with results: "
           f"{json.dumps({c: sum(1 for r in rr if r['condition'] == c) for c in LATENT_CONDS})})",
           "", buf.getvalue(), timing_table(runs), ""]
    text = "\n".join(out)
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "latent_progress.txt"), "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
