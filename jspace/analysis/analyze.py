"""E2-mini analysis: per-arm recall/exact/no_answer + paired per-task tests,
blurb stats, and pointers to qualitative examples.

Usage: python analyze.py <results.jsonl>   (needs scipy for Wilcoxon)
"""
import json
import math
import sys
from collections import defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else "sweeps/full/results.jsonl"
rows = [json.loads(l) for l in open(path) if l.strip()]

by_arm = defaultdict(dict)          # arm -> {task_id: row}  (last run wins)
for r in rows:
    by_arm[r["arm"]][r["id"]] = r

arms = sorted(by_arm)
print(f"loaded {len(rows)} rows; arms={arms}; "
      f"tasks/arm={[len(by_arm[a]) for a in arms]}\n")

def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")

print("| arm | n | recall | exact | abstained | no_answer | ctok/run |")
print("|---|---|---|---|---|---|---|")
for a in arms:
    rs = list(by_arm[a].values())
    rec = [r["recall"] for r in rs if r.get("recall") is not None]
    print("| {} | {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.0f} |".format(
        a, len(rs), mean(rec),
        mean([1.0 * r["exact_match"] for r in rs]),
        mean([1.0 * (r["outcome"] == "abstained") for r in rs]),
        mean([1.0 * (r["outcome"] == "no_answer") for r in rs]),
        mean([r["completion_tokens"] for r in rs])))

if "note" in by_arm and "note_jspace" in by_arm:
    common = sorted(set(by_arm["note"]) & set(by_arm["note_jspace"]))
    d = [(t, (by_arm["note_jspace"][t]["recall"] or 0.0)
             - (by_arm["note"][t]["recall"] or 0.0)) for t in common]
    deltas = [x for _, x in d]
    pos = sum(1 for x in deltas if x > 0)
    neg = sum(1 for x in deltas if x < 0)
    tie = len(deltas) - pos - neg
    print(f"\npaired on {len(common)} tasks: mean delta(recall) = "
          f"{mean(deltas):+.4f}  (jspace better on {pos}, worse on {neg}, tie {tie})")
    try:
        from scipy import stats
        if pos + neg:
            sign_p = stats.binomtest(pos, pos + neg, 0.5).pvalue
            print(f"sign test (excl. ties): p = {sign_p:.4f}")
        nz = [x for x in deltas if x != 0]
        if len(nz) >= 5:
            w = stats.wilcoxon(nz)
            print(f"Wilcoxon signed-rank (nonzero deltas, n={len(nz)}): "
                  f"W={w.statistic:.1f}, p={w.pvalue:.4f}")
    except ImportError:
        print("(scipy unavailable: no p-values)")

    # exact-match paired counts too
    de = [(by_arm["note_jspace"][t]["exact_match"],
           by_arm["note"][t]["exact_match"]) for t in common]
    jw = sum(1 for j, n in de if j and not n)
    nw = sum(1 for j, n in de if n and not j)
    print(f"exact-match flips: jspace-only correct {jw}, note-only correct {nw}")

    print("\nbiggest per-task deltas (task, note, jspace):")
    for t, x in sorted(d, key=lambda p: -abs(p[1]))[:8]:
        print(f"  {t}: {by_arm['note'][t]['recall']:.2f} -> "
              f"{by_arm['note_jspace'][t]['recall']:.2f}  ({x:+.2f})")

    # blurb stats
    bl = [r for r in by_arm["note_jspace"].values() if r.get("blurb_chars")]
    if bl:
        print(f"\nblurbs: {len(bl)}/{len(by_arm['note_jspace'])} runs, "
              f"mean {mean([r['blurb_chars'] for r in bl]):.0f} chars, "
              f"mean silent_frac "
              f"{mean([r['blurb_silent_frac'] for r in bl if r.get('blurb_silent_frac') is not None]):.3f}, "
              f"mean entries {mean([r['blurb_entries'] for r in bl]):.1f}")
    errs = [r["id"] for r in by_arm["note_jspace"].values() if r.get("blurb_error")]
    if errs:
        print(f"blurb ERRORS on: {errs}")
