"""Spend meter over llm_calls.jsonl (Tinker has no usage API, so every call
is self-logged by harness/llm.py with token usage and a phase/arm tag).

Rates are the duet-validated Tinker Qwen3.6-35B-A3B prices. The session
budget is a HARD cap across all synchandoff runs: check before launching
anything and abort a wave if projected spend would cross it.

Usage:
  python cost.py            # total + per-tag-prefix breakdown
  python cost.py --by-tag   # full per-tag table
"""
import argparse
import json
import os
from collections import defaultdict

PREFILL_PER_MTOK = 0.36   # duet DUET_PREFILL_RATE
SAMPLE_PER_MTOK = 0.89    # duet DUET_SAMPLE_RATE
BUDGET_USD = 100.0

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.environ.get("SYNCHANDOFF_LLM_LOG", os.path.join(HERE, "llm_calls.jsonl"))


def usd(pt, ct):
    return pt / 1e6 * PREFILL_PER_MTOK + ct / 1e6 * SAMPLE_PER_MTOK


def load(group_depth=None):
    """Aggregate (prompt, completion, calls) per tag. group_depth=N keeps the
    first N ':'-separated tag fields (tags look like p1:plain:k12:<iid>)."""
    agg = defaultdict(lambda: [0, 0, 0])
    if not os.path.exists(LOG):
        return agg
    with open(LOG) as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            tag = r.get("tag", "?")
            if group_depth:
                tag = ":".join(tag.split(":")[:group_depth])
            u = r.get("usage") or {}
            a = agg[tag]
            a[0] += u.get("prompt_tokens", 0)
            a[1] += u.get("completion_tokens", 0)
            a[2] += 1
    return agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--by-tag", action="store_true", help="full per-tag table")
    args = ap.parse_args()
    agg = load(group_depth=None if args.by_tag else 3)
    rows = sorted(agg.items(), key=lambda kv: -usd(kv[1][0], kv[1][1]))
    tp = tc = tn = 0
    for tag, (pt, ct, n) in rows:
        tp, tc, tn = tp + pt, tc + ct, tn + n
        print(f"{usd(pt, ct):8.3f}$  {pt/1e6:7.2f}M in {ct/1e6:6.2f}M out {n:5d} calls  {tag}")
    total = usd(tp, tc)
    print(f"\nTOTAL: ${total:.2f}  ({tp/1e6:.1f}M prompt + {tc/1e6:.1f}M completion, {tn} calls)")
    print(f"BUDGET: ${BUDGET_USD:.0f}  remaining: ${BUDGET_USD - total:.2f}")
    if total > BUDGET_USD * 0.8:
        print("WARNING: past 80% of budget")


if __name__ == "__main__":
    main()
