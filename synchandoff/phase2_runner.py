"""Phase 2: fresh agent B finishes the episode under a condition.

Per (instance, condition, k, m): rebuild the out-of-sync env, replay A's
frozen end-state patch (same state for every condition — the paired design),
run the tests once for the CURRENT failure output B sees, hand B the
condition's precomputed artifact, run B with tool budget m, then score:
    SR       harness-run tests pass (vs gold_summary)
    LA_file  B's diff touches the out-of-sync file
    LA_func  the target function's text changed from A's end state
    turns    tool calls B used
All judge-free. Results land in runs/<instance>/<condition>_k<k>_m<m>/.

floor uses the SAME A end state with no artifact (B alone, mid-task repo).

Usage:
  python phase2_runner.py --k 8 --m 8 --conditions floor,ceiling,oracle [--limit 2]
"""
import argparse
import json
import os

from handoff import arms as A
from harness import instances as I
from harness.agent import run_agent
from harness.env import InstanceEnv, tests_pass
from harness.prompts import build_prompts

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN = os.path.join(HERE, "phase1_frozen")
ARTIFACTS = os.path.join(HERE, "artifacts")
RUNS = os.path.join(HERE, "runs")
LOG_CAP = 12800


def family_of(condition):
    return "board" if condition in A.BOARD_FAMILY else "plain"


def extract_fm(text, fm_name):
    """The `def fm_name` block, by the same line-scan the aligner uses."""
    lines = (text or "").split("\n")
    out, indent = [], None
    for line in lines:
        if indent is None:
            if f"def {fm_name}" in line:
                indent = len(line) - len(line.lstrip())
                out.append(line)
            continue
        if line.strip() == "":
            out.append(line)
            continue
        if len(line) - len(line.lstrip()) <= indent and out:
            break
        out.append(line)
    return "\n".join(out).rstrip()


def current_failure_log(env):
    summary, raw = env.run_tests()
    start = "test session starts"
    if start in raw:
        raw = "==== " + raw[raw.index(start):]
    if len(raw) > LOG_CAP:
        raw = "[... earlier log omitted ...] " + raw[-(LOG_CAP - 100):]
    return summary, raw


def run_one(inst, condition, k, m):
    iid = inst["instance_id"]
    family = family_of(condition)
    run_d = os.path.join(RUNS, iid, f"{condition}_k{k}_m{m}")
    if os.path.exists(os.path.join(run_d, "result.json")):
        print(f"  [skip, done] {condition} {iid[:50]}")
        return

    frozen_d = os.path.join(FROZEN, iid, f"{family}_k{k}")
    with open(os.path.join(frozen_d, "repo_state.patch")) as f:
        patch = f.read()

    artifact = None
    if condition != "floor":
        art_f = os.path.join(ARTIFACTS, iid, f"{family}_k{k}", f"{condition}.txt")
        with open(art_f) as f:
            artifact = f.read()

    env = InstanceEnv(inst)
    try:
        env.start()
        env.setup_out_of_sync()
        env.apply_patch(patch)
        pre_summary, log = current_failure_log(env)
        baseline_fm = extract_fm(env.read_file(env.pyfile) or "", inst["fm_name"])

        system, user = build_prompts(inst, m, phase="phase2", artifact=artifact,
                                     current_error_log=log)
        result = run_agent(env, system, user, tool_budget=m,
                           tag=f"p2:{condition}:k{k}:m{m}:{iid}")

        post_summary, _ = env.run_tests()
        diff = env.agent_diff()
        gold = I.parse_summary(inst["gold_summary"])
        pyfile_rel = inst["pyfile_path"].split("test_repo/")[1]
        post_fm = extract_fm(env.read_file(env.pyfile) or "", inst["fm_name"])

        out = {
            "instance_id": iid, "condition": condition, "k": k, "m": m,
            "family": family,
            "success": tests_pass(post_summary, gold),
            "pre_test_summary": pre_summary,
            "post_test_summary": post_summary,
            "la_file": pyfile_rel in diff["files"],
            "la_func": post_fm != baseline_fm,
            "tool_calls_used": result["tool_calls_used"],
            "stop_reason": result["stop_reason"],
            "usage": result["usage"],
            "final_text": result["final_text"],
            "files_touched": diff["files"],
        }
        os.makedirs(run_d, exist_ok=True)
        with open(os.path.join(run_d, "traj.jsonl"), "w") as f:
            for ev in result["events"]:
                f.write(json.dumps(ev) + "\n")
        with open(os.path.join(run_d, "result.json"), "w") as f:
            json.dump(out, f, indent=1)
        print(f"  [{condition:>11}] {iid[:50]}: SR={out['success']} "
              f"la_file={out['la_file']} la_func={out['la_func']} calls={out['tool_calls_used']}")
    finally:
        env.stop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="pilot_candidates.json")
    ap.add_argument("--split", default="callee")
    ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--m", type=int, required=True)
    ap.add_argument("--conditions", default="floor,ceiling,oracle")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    with open(args.candidates) as f:
        wanted = [c["instance_id"] for c in json.load(f)]
    if args.limit:
        wanted = wanted[:args.limit]
    by_id = {i["instance_id"]: i for i in I.load_instances(args.split)}
    print(f"phase2: {len(wanted)} instances x {conditions}, k={args.k} m={args.m}")
    for iid in wanted:
        for cond in conditions:
            run_one(by_id[iid], cond, args.k, args.m)


if __name__ == "__main__":
    main()
