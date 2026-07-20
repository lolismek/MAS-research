"""Belief-state bin labeler (plan sec. 5.3 — SECONDARY, post-hoc robustness cut).

Labels each frozen phase-1 trajectory with A's end-of-shift belief about the
failure cause:
  T  true belief  — A identified the actual out-of-sync function as the cause
  F  false belief — A committed to a WRONG diagnosis
  0  no belief    — A held no firm diagnosis
Recorded, never engineered (selection does not read these). The gold cause is
known per construction: fm_name in pyfile_path. A hand-checked slice (20,
stratified) validates the labels before any bin-level claim is made.

Usage: python bins.py --k 8 [--family plain] [--limit 5]
Writes bin label into phase1_frozen/<iid>/<family_k>/bin.json
"""
import argparse
import json
import os
import re

from build_artifacts import load_frozen
from handoff import arms as A
from harness import instances as I
from harness import llm

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN = os.path.join(HERE, "phase1_frozen")

LABEL_SYS = (
    "You are reading the working log of an agent that investigated a failing test in a "
    "Python repository but had to stop early. The TRUE cause (known to us, not to the "
    "agent) was: the {fm_type} `{fm_name}` in `{pyfile}` was out of sync with the rest "
    "of the repository.\n"
    "From the log alone, decide the agent's END-OF-SHIFT belief about the cause:\n"
    "T — it identified `{fm_name}` in `{pyfile}` (or that exact code) as the cause\n"
    "F — it committed to a DIFFERENT, wrong diagnosis (wrong file/function/mechanism)\n"
    "0 — it held no firm diagnosis by the end (still exploring, or explicitly unsure)\n"
    "Think it through, then output exactly one line:\n"
    "BIN: <T|F|0> | <one-sentence justification>"
)

_BIN = re.compile(r"BIN\s*:\s*([TF0])\s*\|\s*(.+)")


def label_one(inst, frozen, tag):
    log = A.render_events(frozen["events"], total_chars=A.CEILING_CHARS)
    sys_p = LABEL_SYS.format(fm_type=inst["fm_type"], fm_name=inst["fm_name"],
                             pyfile=I.container_pyfile_path(inst))
    msg = llm.chat([{"role": "system", "content": sys_p},
                    {"role": "user", "content": f"<working_log>\n{log}\n</working_log>"}],
                   tag=tag)
    m = _BIN.search(msg.get("content") or "")
    if not m:
        return {"bin": "?", "why": "no BIN line", "raw": (msg.get("content") or "")[-300:]}
    return {"bin": m.group(1), "why": m.group(2).strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--family", default="plain")
    ap.add_argument("--split", default="callee")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    by_id = {i["instance_id"]: i for i in I.load_instances(args.split)}
    ids = sorted(os.listdir(FROZEN)) if os.path.isdir(FROZEN) else []
    if args.limit:
        ids = ids[:args.limit]
    for iid in ids:
        d = os.path.join(FROZEN, iid, f"{args.family}_k{args.k}")
        out_f = os.path.join(d, "bin.json")
        if not os.path.isdir(d) or os.path.exists(out_f) or iid not in by_id:
            continue
        frozen = load_frozen(iid, args.family, args.k)
        if frozen is None:
            continue
        res = label_one(by_id[iid], frozen, tag=f"bin:{iid}")
        with open(out_f, "w") as f:
            json.dump(res, f, indent=1)
        print(f"  [{res['bin']}] {iid[:60]}: {res['why'][:90]}")


if __name__ == "__main__":
    main()
