"""Phase 1: run agent A for k tool calls and freeze everything phase 2 needs.

Per (instance, family, k): out-of-sync env -> A runs with the phase-1 prompt
and hard tool budget k -> we freeze
    traj.jsonl        the full event trajectory (arms consume this)
    repo_state.patch  git diff of whatever A changed (phase 2 replays it)
    meta.json         stop reason, usage, post-A test summary (G3 audit: did
                      A solve it? make progress?), files touched
Frozen once, reused by every bracket/arm/budget — the paired-design backbone.

Families: 'plain' (shared by vanilla/full/sop/down/extract + brackets) and
'board' (A additionally holds add_note/revise_note ledger tools; built at
step 4).

Usage:
  python phase1_runner.py --candidates pilot_candidates.json --k 8 [--limit 2]
"""
import argparse
import json
import os

from harness import instances as I
from harness.agent import run_agent
from harness.env import InstanceEnv
from harness.prompts import build_prompts

HERE = os.path.dirname(os.path.abspath(__file__))


def out_dir(instance_id, family, k):
    return os.path.join(HERE, "phase1_frozen", instance_id, f"{family}_k{k}")


def run_one(inst, k, family="plain"):
    iid = inst["instance_id"]
    d = out_dir(iid, family, k)
    if os.path.exists(os.path.join(d, "meta.json")):
        print(f"  [skip, frozen] {iid}")
        return
    os.makedirs(d, exist_ok=True)
    ledger, extra_tools = None, None
    if family == "board":
        from handoff.arms import BOARD_WRITE_INCENTIVE, make_board_tools
        from harness.ledger import BeliefLedger
        ledger = BeliefLedger()
        extra_tools = make_board_tools(ledger)
    elif family != "plain":
        raise ValueError(f"unknown family {family!r}")

    env = InstanceEnv(inst)
    try:
        env.start()
        env.setup_out_of_sync()
        system, user = build_prompts(inst, k, phase="phase1")
        if family == "board":
            system += BOARD_WRITE_INCENTIVE
        result = run_agent(env, system, user, tool_budget=k, tag=f"p1:{family}:k{k}:{iid}",
                           extra_tools=extra_tools)
        # NOTE: the board arm's end-of-shift write-window (arms.board_wrapup)
        # runs OFFLINE in build_artifacts, not here — the frozen meta stores
        # only what A wrote in-loop.

        summary, _ = env.run_tests()
        diff = env.agent_diff()
        gold = I.parse_summary(inst["gold_summary"])
        from harness.env import tests_pass
        meta = {
            "instance_id": iid, "family": family, "k": k,
            "stop_reason": result["stop_reason"],
            "tool_calls_used": result["tool_calls_used"],
            "usage": result["usage"],
            "final_text": result["final_text"],
            "post_A_test_summary": summary,
            "post_A_solved": tests_pass(summary, gold),
            "files_touched": diff["files"],
        }
        if ledger is not None:
            meta["ledger"] = ledger.to_json()
        with open(os.path.join(d, "traj.jsonl"), "w") as f:
            for ev in result["events"]:
                f.write(json.dumps(ev) + "\n")
        with open(os.path.join(d, "repo_state.patch"), "w") as f:
            f.write(diff["diff"] or "")
        with open(os.path.join(d, "meta.json"), "w") as f:
            json.dump(meta, f, indent=1)
        print(f"  [frozen] {iid}: stop={meta['stop_reason']} calls={meta['tool_calls_used']} "
              f"solved={meta['post_A_solved']} touched={meta['files_touched']}")
    finally:
        env.stop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="pilot_candidates.json")
    ap.add_argument("--split", default="callee")
    ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--family", default="plain")
    ap.add_argument("--limit", type=int, default=None, help="run only the first N (smoke)")
    args = ap.parse_args()

    with open(args.candidates) as f:
        wanted = [c["instance_id"] for c in json.load(f)]
    if args.limit:
        wanted = wanted[:args.limit]
    by_id = {i["instance_id"]: i for i in I.load_instances(args.split)}
    print(f"phase1: {len(wanted)} instances, family={args.family}, k={args.k}")
    for iid in wanted:
        run_one(by_id[iid], args.k, args.family)


if __name__ == "__main__":
    main()
