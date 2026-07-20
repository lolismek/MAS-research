"""Precompute handoff artifacts for every (frozen instance, arm) offline.

Pure transformation of cached phase-1 data (at most 1-2 LLM calls per arm,
zero environment time): artifacts/<instance_id>/<family_k>/<arm>.txt (+ .json
aux). Idempotent — existing artifacts are skipped, so this can be re-run
after adding arms. Phase 2 then only READS these files.

Usage:
  python build_artifacts.py --k 8 [--arms vanilla,sop,...] [--limit 2]
"""
import argparse
import json
import os

from handoff import arms as A
from harness import instances as I
from harness.prompts import build_prompts

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN = os.path.join(HERE, "phase1_frozen")
ARTIFACTS = os.path.join(HERE, "artifacts")


def load_frozen(iid, family, k):
    d = os.path.join(FROZEN, iid, f"{family}_k{k}")
    if not os.path.exists(os.path.join(d, "meta.json")):
        return None
    with open(os.path.join(d, "meta.json")) as f:
        meta = json.load(f)
    events = []
    with open(os.path.join(d, "traj.jsonl")) as f:
        for line in f:
            events.append(json.loads(line))
    return {"events": events, "meta": meta}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--split", default="callee")
    ap.add_argument("--arms", default=",".join(a for a in A.ARMS if a != "floor"))
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    wanted_arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    by_id = {i["instance_id"]: i for i in I.load_instances(args.split)}
    frozen_ids = sorted(os.listdir(FROZEN)) if os.path.isdir(FROZEN) else []
    if args.limit:
        frozen_ids = frozen_ids[:args.limit]
    built = skipped = missing = 0
    for iid in frozen_ids:
        inst = by_id.get(iid)
        if inst is None:
            continue
        # the task block down's asker sees = the phase-2 system prompt's task part
        task_block, _ = build_prompts(inst, budget=0, phase="phase2")
        for arm in wanted_arms:
            family = "board" if arm in A.BOARD_FAMILY else "plain"
            out_d = os.path.join(ARTIFACTS, iid, f"{family}_k{args.k}")
            out_f = os.path.join(out_d, f"{arm}.txt")
            if os.path.exists(out_f):
                skipped += 1
                continue
            frozen = load_frozen(iid, family, args.k)
            if frozen is None:
                missing += 1
                continue
            artifact, aux = A.build_artifact(arm, frozen, inst, task_block=task_block)
            os.makedirs(out_d, exist_ok=True)
            with open(out_f, "w") as f:
                f.write(artifact or "")
            if aux:
                with open(out_f.replace(".txt", ".json"), "w") as f:
                    json.dump(aux, f, indent=1)
            built += 1
            print(f"  [{arm:>11}] {iid[:60]}: {len(artifact or '')} chars")
    print(f"built={built} skipped={skipped} missing_frozen={missing}")


if __name__ == "__main__":
    main()
