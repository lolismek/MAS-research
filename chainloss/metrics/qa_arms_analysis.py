"""E1-mini analysis: paired per-task comparison of the hand-off Q&A arms
(note_randq / note_epiq, N=2) against the baseline `note` N=2 cell.

Baseline rows come from sweeps/full/results.jsonl (the 2026-07-30 main run);
treatment rows from sweeps/<sweep>/results.jsonl. Pairing is per task id.
Tests: exact two-sided sign test on per-task recall deltas (no scipy in env)
plus a Wilcoxon signed-rank normal approximation (ties dropped, zero-deltas
dropped, average ranks).

Run:  conda run -n autogen_gc python chainloss/metrics/qa_arms_analysis.py [sweep]
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load(path, arm, n=2):
    rows = {}
    for line in open(path):
        r = json.loads(line)
        if r["arm"] == arm and r["n"] == n:
            rows[r["id"]] = r
    return rows


def sign_test(deltas):
    """Exact two-sided binomial sign test on nonzero deltas."""
    pos = sum(1 for d in deltas if d > 0)
    neg = sum(1 for d in deltas if d < 0)
    m = pos + neg
    if m == 0:
        return pos, neg, 1.0
    k = min(pos, neg)
    p = sum(math.comb(m, i) for i in range(k + 1)) / 2 ** m * 2
    return pos, neg, min(1.0, p)


def wilcoxon(deltas):
    """Signed-rank test, normal approximation with tie correction; None if <6 nonzero."""
    d = [x for x in deltas if x != 0]
    nz = len(d)
    if nz < 6:
        return nz, None
    ranked = sorted(range(nz), key=lambda i: abs(d[i]))
    ranks = [0.0] * nz
    i = 0
    while i < nz:
        j = i
        while j + 1 < nz and abs(d[ranked[j + 1]]) == abs(d[ranked[i]]):
            j += 1
        avg = (i + j) / 2 + 1
        for t in range(i, j + 1):
            ranks[ranked[t]] = avg
        i = j + 1
    wp = sum(r for r, x in zip(ranks, d) if x > 0)
    mu = nz * (nz + 1) / 4
    sigma = math.sqrt(nz * (nz + 1) * (2 * nz + 1) / 24)
    if sigma == 0:
        return nz, 1.0
    z = (wp - mu) / sigma
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return nz, p


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def summarize(name, rows):
    rs = list(rows.values())
    return dict(
        arm=name, n_tasks=len(rs),
        recall=mean([r["recall"] or 0.0 for r in rs]),
        exact=mean([1.0 if r["exact_match"] else 0.0 for r in rs]),
        abstained=mean([1.0 if r["outcome"] == "abstained" else 0.0 for r in rs]),
        no_answer=mean([1.0 if r["outcome"] == "no_answer" else 0.0 for r in rs]),
        ctok=mean([r["completion_tokens"] for r in rs]),
        qa_ctok=mean([r.get("qa_completion_tokens", 0) for r in rs]),
        cost=sum(r["cost_usd"] for r in rs))


def main():
    sweep = sys.argv[1] if len(sys.argv) > 1 else "e1_qa"
    base = load(os.path.join(ROOT, "sweeps", "full", "results.jsonl"), "note")
    print(f"baseline note/n2: {len(base)} tasks")
    print("| arm | n | recall | exact | abstain | no_answer | ctok | qa_ctok | Δrecall (paired) | up/down | sign p | wilcoxon p |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    s = summarize("note (baseline)", base)
    print("| {arm} | {n_tasks} | {recall:.3f} | {exact:.3f} | {abstained:.3f} | "
          "{no_answer:.3f} | {ctok:.0f} | — | — | — | — | — |".format(**s))
    for arm in ("note_randq", "note_epiq"):
        rows = load(os.path.join(ROOT, "sweeps", sweep, "results.jsonl"), arm)
        common = sorted(set(base) & set(rows))
        deltas = [(rows[t]["recall"] or 0.0) - (base[t]["recall"] or 0.0) for t in common]
        pos, neg, p_sign = sign_test(deltas)
        nz, p_w = wilcoxon(deltas)
        s = summarize(arm, rows)
        print("| {arm} | {n_tasks} | {recall:.3f} | {exact:.3f} | {abstained:.3f} | "
              "{no_answer:.3f} | {ctok:.0f} | {qa_ctok:.0f} | {d:+.3f} | {up}/{down} | "
              "{ps:.3f} | {pw} |".format(
                  d=mean(deltas), up=pos, down=neg, ps=p_sign,
                  pw=f"{p_w:.3f}" if p_w is not None else f"n/a (nz={nz})", **s))
        print(f"  [{arm}] paired on {len(common)} tasks, spend ${s['cost']:.2f}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
