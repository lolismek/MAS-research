"""Env-fidelity audit (G1 over every candidate, no LLM): for each instance,
boot the env and check that

  broken state  -> pytest (passed, failed, error) == original_summary
  gold restore  -> pytest (passed, failed, error) == gold_summary

Any mismatch means the substrate would score garbage for that instance —
drop or debug it before spending tokens. Results in audit_results/<iid>.json
(idempotent; delete a file to re-audit).

Usage:
  python audit_envs.py [--candidates pilot_candidates.json] [--broken-only]
"""
import argparse
import json
import os

from harness import instances as I
from harness.env import InstanceEnv

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "audit_results")


def key(s):
    return [s.get("passed", 0), s.get("failed", 0), s.get("error", 0)]


def audit_one(inst, broken_only=False):
    iid = inst["instance_id"]
    path = os.path.join(OUT, f"{iid}.json")
    if os.path.exists(path):
        r = json.load(open(path))
        print(f"  [cached] {iid[:60]}  broken_ok={r['broken_ok']} gold_ok={r.get('gold_ok')}")
        return r
    orig = I.parse_summary(inst["original_summary"])
    gold = I.parse_summary(inst["gold_summary"])
    r = {"instance_id": iid, "expected_broken": key(orig), "expected_gold": key(gold)}
    env = InstanceEnv(inst)
    try:
        env.start()
        env.setup_out_of_sync()
        r["editable_ok"] = env.editable_ok
        summary, out = env.run_tests()
        r["got_broken"] = key(summary)
        r["broken_ok"] = r["got_broken"] == r["expected_broken"]
        if not r["broken_ok"]:
            r["broken_tail"] = out[-1500:]
        if not broken_only:
            env.restore_gold()
            summary, out = env.run_tests()
            r["got_gold"] = key(summary)
            r["gold_ok"] = r["got_gold"] == r["expected_gold"]
            if not r["gold_ok"]:
                r["gold_tail"] = out[-1500:]
    except Exception as e:
        r["error"] = f"{type(e).__name__}: {e}"
        r["broken_ok"] = False
    finally:
        env.stop()
    with open(path, "w") as f:
        json.dump(r, f, indent=1)
    print(f"  [audit] {iid[:60]}  broken_ok={r['broken_ok']} gold_ok={r.get('gold_ok')}"
          + (f"  ERR={r.get('error', '')[:80]}" if r.get("error") else ""))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="pilot_candidates.json")
    ap.add_argument("--split", default="callee")
    ap.add_argument("--broken-only", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    with open(args.candidates) as f:
        wanted = [c["instance_id"] for c in json.load(f)]
    by_id = {i["instance_id"]: i for i in I.load_instances(args.split)}
    results = [audit_one(by_id[iid], args.broken_only) for iid in wanted]
    ok = [r for r in results if r["broken_ok"] and r.get("gold_ok", True)]
    print(f"\nfaithful: {len(ok)}/{len(results)}")
    for r in results:
        if r not in ok:
            print(f"  BAD {r['instance_id'][:65]} broken={r.get('got_broken')} "
                  f"vs {r['expected_broken']} gold={r.get('got_gold')} vs {r['expected_gold']}")


if __name__ == "__main__":
    main()
