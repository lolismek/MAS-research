"""Pilot aggregation for the review gate (plan sections 8 and 12.3).

Reads phase1_frozen/ (k-sweep) and runs/ (bracket episodes, produced by
phase2_runner) and prints the numbers the go/no-go decision needs:

G3 (k calibration), per k:
  - solved-by-A rate            (want < 30%)
  - non-trivial-findings rate   (want 60-80%; offline proxy: A touched a file
    OR its final text / trajectory shows it reached the target file)
G2 (headroom), per bracket at the chosen k, m:
  - SR (tests pass), LA_file / LA_func, mean tool calls used
  - pass rule: ceiling/oracle beat floor by >= 15 pts LA_func or >= 10 SR

Usage: python pilot_report.py [--runs runs] [--frozen phase1_frozen]
"""
import argparse
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def load_metas(frozen_dir):
    metas = []
    if not os.path.isdir(frozen_dir):
        return metas
    for iid in sorted(os.listdir(frozen_dir)):
        d = os.path.join(frozen_dir, iid)
        if not os.path.isdir(d):
            continue
        for fam in sorted(os.listdir(d)):
            p = os.path.join(d, fam, "meta.json")
            if os.path.exists(p):
                with open(p) as f:
                    metas.append(json.load(f))
    return metas


def nontrivial(meta):
    """Offline proxy for 'A carried non-trivial findings': it modified the
    repo, or its trajectory reached the out-of-sync file. The hand audit at
    the review gate refines this; this is the census number."""
    if meta.get("files_touched"):
        return True
    for ev_line in meta.get("target_file_hits", []):
        return True
    return bool(meta.get("target_file_hit"))


def g3_table(metas):
    by_k = defaultdict(list)
    for m in metas:
        by_k[(m["family"], m["k"])].append(m)
    print("=== G3: phase-1 k calibration")
    print(f"{'family':>7} {'k':>3} {'n':>4} {'solved_by_A':>12} {'touched_repo':>13} {'budget_stop':>12}")
    for (fam, k), ms in sorted(by_k.items()):
        n = len(ms)
        solved = sum(1 for m in ms if m.get("post_A_solved"))
        touched = sum(1 for m in ms if m.get("files_touched"))
        budget = sum(1 for m in ms if m.get("stop_reason") == "budget")
        print(f"{fam:>7} {k:>3} {n:>4} {solved:>5} ({100*solved/n:>4.0f}%) {touched:>6} ({100*touched/n:>4.0f}%) {budget:>5} ({100*budget/n:>4.0f}%)")
    print()


def load_runs(runs_dir):
    runs = []
    if not os.path.isdir(runs_dir):
        return runs
    for root, _, files in os.walk(runs_dir):
        for fn in files:
            if fn == "result.json":
                with open(os.path.join(root, fn)) as f:
                    runs.append(json.load(f))
    return runs


def g2_table(runs, metas=()):
    """Per (k,m) block, split by whether A had ALREADY solved at the end of
    phase 1: on A-solved instances the replayed repo state carries the fix, so
    every condition scores SR=100% regardless of the note — only the A-unsolved
    slice discriminates the brackets/arms (2026-07-20 pilot finding)."""
    solved_by_A = {(m["instance_id"], m["k"]): m.get("post_A_solved")
                   for m in metas if m.get("family") == "plain"}
    by_block = defaultdict(lambda: defaultdict(list))
    for r in runs:
        a_solved = solved_by_A.get((r["instance_id"], r["k"]))
        abin = "A_solved" if a_solved else ("A_unsolved" if a_solved is not None else "?")
        by_block[(r["k"], r["m"])][(abin, r["condition"])].append(r)
    print("=== G2: brackets/arms (phase-2 outcomes)")
    for (k, m), groups in sorted(by_block.items()):
        print(f"--- k={k} m={m}")
        print(f"{'slice':>11} {'condition':>12} {'n':>4} {'SR':>6} {'LA_file':>8} {'LA_func':>8} {'mean_calls':>11}")
        for (abin, cond), rs in sorted(groups.items()):
            n = len(rs)
            sr = sum(1 for r in rs if r.get("success")) / n
            laf = sum(1 for r in rs if r.get("la_file")) / n
            lam = sum(1 for r in rs if r.get("la_func")) / n
            calls = sum(r.get("tool_calls_used", 0) for r in rs) / n
            print(f"{abin:>11} {cond:>12} {n:>4} {100*sr:>5.0f}% {100*laf:>7.0f}% {100*lam:>7.0f}% {calls:>11.1f}")
    print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen", default=os.path.join(HERE, "phase1_frozen"))
    ap.add_argument("--runs", default=os.path.join(HERE, "runs"))
    args = ap.parse_args()
    metas = load_metas(args.frozen)
    print(f"loaded {len(metas)} frozen phase-1 metas\n")
    if metas:
        g3_table(metas)
    runs = load_runs(args.runs)
    print(f"loaded {len(runs)} phase-2 results\n")
    if runs:
        g2_table(runs, metas)
