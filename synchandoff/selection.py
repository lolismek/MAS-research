"""Pilot candidate selection: an easy-skewed subsample of syncbench_300.

Easiness is estimated OFFLINE from dataset fields only (no model runs), per
plan section 6:
  - small gold-vs-original edit (the repair itself is small)
  - failure mode is failing tests rather than a collection error (collection
    errors mean the module doesn't even import — usually deeper drift)
  - few failing tests
  - light, pure-python repos (also keeps Docker wall-clock sane)
The output is a ranked candidate list; nothing about belief-state bins enters
selection (bins are recorded post-hoc, not engineered).
"""
import argparse
import difflib
import json
import os

from harness import instances as I

# Repos whose images are light and pure-python enough for fast test cycles.
# Heavy ML stacks (transformers, pycaret, FLAML, mlflow, optuna, sklearn,
# whisper) burn minutes per pytest run and add env flakiness, not signal.
LIGHT_REPOS = {"fastapi", "flask", "requests", "black", "pylint", "pytest",
               "scrapy", "sphinx", "sympy", "seaborn", "pillow", "gym", "spacy",
               "matplotlib"}


def edit_ratio(a, b):
    """1 - similarity of the two function versions (0 = identical)."""
    return 1.0 - difflib.SequenceMatcher(None, a, b).ratio()


def score(inst):
    """Lower = easier. Components normalized to roughly [0, 1]."""
    orig = I.parse_summary(inst["original_summary"])
    gold = I.parse_summary(inst["gold_summary"])
    collection_error = 1.0 if orig.get("error", 0) > 0 else 0.0
    n_failing = orig.get("failed", 0) + orig.get("error", 0)
    frac_failing = n_failing / max(1, gold.get("passed", 1))
    er = edit_ratio(inst["original_code"], inst["gold_code"])
    size_penalty = min(1.0, len(inst["gold_code"]) / 8000)
    return 1.5 * collection_error + 1.0 * er + 0.5 * min(1.0, frac_failing) + 0.5 * size_penalty


def repo_of(inst):
    return inst["repo_url"].rstrip("/").split("/")[-1]


def select(split="callee", n=30, per_repo_cap=4):
    insts = [i for i in I.load_instances(split) if repo_of(i) in LIGHT_REPOS]
    ranked = sorted(insts, key=score)
    picked, counts = [], {}
    for inst in ranked:
        r = repo_of(inst)
        if counts.get(r, 0) >= per_repo_cap:
            continue
        picked.append(inst)
        counts[r] = counts.get(r, 0) + 1
        if len(picked) >= n:
            break
    return picked


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="callee")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--out", default="pilot_candidates.json")
    args = ap.parse_args()
    picked = select(args.split, args.n)
    payload = [{"instance_id": p["instance_id"], "repo": repo_of(p),
                "score": round(score(p), 3),
                "original_summary": p["original_summary"]} for p in picked]
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=1)
    print(f"{len(picked)} candidates -> {args.out}")
    for p in payload:
        print(f"  {p['score']:.3f} {p['instance_id'][:70]}")
