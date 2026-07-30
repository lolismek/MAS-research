"""Self-meter beliefrelay spend from the shared proxy log (Tinker has no usage API).

Sums tokens for every tag starting with 'br' in calls.jsonl and prices them at the
Tinker console rates for Qwen/Qwen3.6-35B-A3B (2026-06-27). Run standalone or import
total_spend() (the grid runner's budget guard).
"""
import json
import os

CALLS_LOG = os.environ.get(
    "BR_CALLS_LOG",
    "/Users/alexjerpelea/.superset/worktrees/ec13f4a5-e2f8-42ae-9d29-8076a6319e5b/"
    "multi-benchmark-eval/shared/proxy/calls.jsonl")
PREFILL_PER_MTOK = 0.36
SAMPLE_PER_MTOK = 0.89
HARD_CAP_USD = 20.0
ABORT_AT_USD = 18.0   # leave headroom so in-flight calls can't blow the cap


def total_spend(prefix="br"):
    pt = ct = n = 0
    by_tag = {}
    if os.path.exists(CALLS_LOG):
        for line in open(CALLS_LOG):
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            tag = r.get("tag") or ""
            if not tag.startswith(prefix):
                continue
            p = r.get("prompt_tokens") or 0
            c = r.get("completion_tokens") or 0
            pt += p
            ct += c
            n += 1
            t = by_tag.setdefault(tag.split("_")[1] if "_" in tag else tag,
                                  dict(calls=0, pt=0, ct=0))
            t["calls"] += 1
            t["pt"] += p
            t["ct"] += c
    cost = pt / 1e6 * PREFILL_PER_MTOK + ct / 1e6 * SAMPLE_PER_MTOK
    return dict(calls=n, prompt_tokens=pt, completion_tokens=ct,
                cost_usd=round(cost, 4), by_group=by_tag)


if __name__ == "__main__":
    s = total_spend()
    print(f"beliefrelay spend: ${s['cost_usd']:.4f}  "
          f"({s['calls']} calls, {s['prompt_tokens']} pt / {s['completion_tokens']} ct)")
    for g, t in sorted(s["by_group"].items()):
        c = t["pt"] / 1e6 * PREFILL_PER_MTOK + t["ct"] / 1e6 * SAMPLE_PER_MTOK
        print(f"  {g:12s} ${c:7.4f}  {t['calls']:5d} calls")
