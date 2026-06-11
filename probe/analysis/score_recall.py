"""Phase-4 recall scoring: the headline numbers. No model needed.

Run:  python -m probe.analysis.score_recall --run main [--llm-judge]

Per (context, arm, sample): each planted fact is scored recalled/not in B's
output by the same string matcher used for verbalized labeling. Facts are
split by the capture-time label:
  verbalized   — in the note text (sanity: should be ~equal across arms)
  unverbalized — only in A's context (the hypothesis test: arm 2 vs 1, ≤ 5)

Aggregation: recall per context = mean over (facts in split × samples);
bootstrap CI (percentile, 1000 resamples) over contexts. Cost accounting
reports payload tokens per arm.

--llm-judge: for facts that fail the string match, ask a Perplexity model
whether B's text reflects the fact (rubric = fact summary). String match
stays authoritative for positives; the judge can only add recalls, and all
judge verdicts are cached + logged for spot-checking.
"""

import argparse
import json
import random
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

from probe.common import RUNS_DIR, perplexity_api_key, read_json, write_json
from probe.contexts.facts import fact_matches

_ARM_RANK = {"0": 0, "1": 1, "2": 2, "2i": 3, "3": 4, "3i": 5,
             "5": 90, "5t": 91}
_ARM_LABELS = {
    "0": "arm 0 — no note (floor)",
    "1": "arm 1 — note only (baseline)",
    "2": "arm 2 — note + rolled latents",
    "2i": "arm 2i — rolled latents in place of note",
    "3": "arm 3 — note + note-suffix states",
    "3i": "arm 3i — note-suffix states in place of note",
    "5": "arm 5 — note + raw context (ceiling)",
    "5t": "arm 5t — note + truncated raw context",
}


def arm_sort_key(arm: str):
    if arm in _ARM_RANK:
        return (_ARM_RANK[arm], 0)
    m = re.fullmatch(r"4(i?)k(\d+)", arm)
    if m:  # alongside 4k* then in-place 4ik*, ascending k, between 3i and 5
        return (10 + (1 if m.group(1) else 0), int(m.group(2)))
    return (99, 0)


def arm_label(arm: str) -> str:
    if arm in _ARM_LABELS:
        return _ARM_LABELS[arm]
    m = re.fullmatch(r"4(i?)k(\d+)", arm)
    if m and m.group(1):
        return f"arm {arm} — selected context states (k={m.group(2)}) in place of note"
    if m:
        return f"arm {arm} — note + selected context states (k={m.group(2)})"
    return f"arm {arm}"


def llm_judge(fact_summary: str, b_text: str, cache: dict, cache_path: Path) -> bool:
    key = f"{fact_summary}||{hash(b_text)}"
    if key in cache:
        return cache[key]["verdict"]
    api_key = perplexity_api_key()
    if not api_key:
        raise RuntimeError("PERPLEXITY_API_KEY not found for --llm-judge")
    body = json.dumps({
        "model": "sonar",
        "messages": [{
            "role": "user",
            "content": (
                "Does the following agent handoff response reflect this fact "
                f"(restated, paraphrased, or used in its plan)?\nFACT: {fact_summary}\n\n"
                f"RESPONSE:\n{b_text}\n\nAnswer with exactly YES or NO."
            ),
        }],
        "max_tokens": 5,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        "https://api.perplexity.ai/chat/completions", data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        answer = json.load(r)["choices"][0]["message"]["content"].strip().upper()
    verdict = answer.startswith("YES")
    cache[key] = {"verdict": verdict, "fact": fact_summary, "answer": answer}
    write_json(cache, cache_path)
    return verdict


def bootstrap_ci(per_context_values: list[float], n_boot: int = 1000, seed: int = 7):
    rng = random.Random(seed)
    if not per_context_values:
        return (float("nan"), float("nan"))
    means = []
    n = len(per_context_values)
    for _ in range(n_boot):
        sample = [per_context_values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return (means[int(0.025 * n_boot)], means[int(0.975 * n_boot)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="main")
    ap.add_argument("--contexts", default="data/contexts")
    ap.add_argument("--llm-judge", action="store_true")
    args = ap.parse_args()

    run_dir = RUNS_DIR / args.run
    arms_dir = run_dir / "arms"
    out_dir = run_dir / "analysis"
    cache_path = out_dir / "judge_cache.json"
    judge_cache = read_json(cache_path) if cache_path.exists() else {}

    contexts = {p.stem: read_json(p) for p in sorted(Path(args.contexts).glob("ctx_*.json"))}

    # per arm -> split -> context_id -> list of 0/1 over (fact, sample)
    hits = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    payload_tokens = defaultdict(list)
    arms_seen = set()

    for path in sorted(arms_dir.glob("ctx_*_arm*_s*.json")):
        rec = read_json(path)
        cid, arm = rec["context_id"], rec["arm"]
        ctx = contexts[cid]
        cap = read_json(run_dir / "capture" / f"{cid}.json")
        arms_seen.add(arm)
        payload_tokens[arm].append(rec["payload_tokens"])
        for f in ctx["facts"]:
            # recompute from the note with the CURRENT matcher (not the stored
            # capture-time labels) so matcher fixes apply post-hoc
            split = "verbalized" if fact_matches(f, cap["note"]) else "unverbalized"
            ok = fact_matches(f, rec["text"])
            if not ok and args.llm_judge:
                ok = llm_judge(f["summary"], rec["text"], judge_cache, cache_path)
            hits[arm][split][cid].append(1.0 if ok else 0.0)

    arms = sorted(arms_seen, key=arm_sort_key)
    results = {}
    for arm in arms:
        results[arm] = {"payload_tokens_mean":
                        sum(payload_tokens[arm]) / max(1, len(payload_tokens[arm]))}
        for split in ("verbalized", "unverbalized"):
            per_ctx = [sum(v) / len(v) for v in hits[arm][split].values() if v]
            if not per_ctx:
                results[arm][split] = None
                continue
            mean = sum(per_ctx) / len(per_ctx)
            lo, hi = bootstrap_ci(per_ctx)
            results[arm][split] = {
                "recall": mean, "ci95": [lo, hi], "n_contexts": len(per_ctx),
            }

    # paired per-context deltas vs arm 1, both splits (unverbalized = the
    # alongside hypothesis test; verbalized = the in-place headline)
    deltas = {"unverbalized": {}, "verbalized": {}}
    if "1" in results:
        for split in deltas:
            base = hits["1"][split]
            for arm in arms:
                if arm == "1":
                    continue
                ds = [sum(hits[arm][split][c]) / len(hits[arm][split][c])
                      - sum(base[c]) / len(base[c])
                      for c in base if hits[arm][split].get(c)]
                if ds:
                    lo, hi = bootstrap_ci(ds)
                    deltas[split][arm] = {"mean_delta": sum(ds) / len(ds),
                                          "ci95": [lo, hi]}

    write_json({"results": results,
                "deltas_vs_arm1_unverbalized": deltas["unverbalized"],
                "deltas_vs_arm1_verbalized": deltas["verbalized"]},
               out_dir / "recall.json")

    n_scored = len({cid for arm in hits.values() for split in arm.values() for cid in split})
    lines = [
        "# Planted-fact recall",
        "",
        f"run: `{args.run}` — {n_scored} contexts scored, "
        f"llm_judge={'on' if args.llm_judge else 'off'}",
        "",
        "| arm | payload tok | verbalized recall | unverbalized recall | Δ verb. vs arm 1 | Δ unverb. vs arm 1 |",
        "|---|---|---|---|---|---|",
    ]
    for arm in arms:
        r = results[arm]
        def fmt(s):
            if not r.get(s):
                return "—"
            return f"{r[s]['recall']:.3f} [{r[s]['ci95'][0]:.3f}, {r[s]['ci95'][1]:.3f}]"
        def fmt_d(split):
            d = deltas[split].get(arm)
            if not d:
                return "—"
            return f"{d['mean_delta']:+.3f} [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}]"
        lines.append(f"| {arm_label(arm)} | {r['payload_tokens_mean']:.0f} | "
                     f"{fmt('verbalized')} | {fmt('unverbalized')} | "
                     f"{fmt_d('verbalized')} | {fmt_d('unverbalized')} |")
    lines += [
        "",
        "Reading guide (PROBE_PLAN.md §why-arm-5-matters and §in-place-arms): "
        "alongside arms — 2/3/4 ≈ 5 at few tokens → latent compression win; "
        "≈ 1 while 5 ≫ 1 → info exists but training-free injection fails (v2 trained compressor); "
        "5 ≈ 1 → probe construction broken. Verbalized recall ≈ equal across "
        "alongside arms (sanity). In-place arms — the VERBALIZED column is the "
        "headline: 3i ≈ 1 → substitution works, proceed to 4i; "
        "3i ≈ 2i ≈ 0 → level (i) can't deliver even self-generated content "
        "(level (ii) or v2). Arm 0 ≪ arm 1 on verbalized validates the floor.",
    ]
    report = "\n".join(lines)
    (out_dir / "recall_report.md").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "recall_report.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
