"""Intrinsic probe battery (plan sec. 5.2 — SECONDARY, mechanism diagnostic).

Judges each artifact on two axes, never headline:
  fidelity      which of A's actual findings (from its frozen trajectory)
                survive into the artifact
  confabulation claims in the artifact that A's trajectory does NOT support
LLM-judged (the only judge-dependent metric family, per plan sec. 10.4).

Usage: python probes.py --k 8 [--arms vanilla,sop] [--limit 2]
Writes artifacts/<iid>/<family_k>/<arm>.probe.json
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
ARTIFACTS = os.path.join(HERE, "artifacts")

JUDGE_SYS = (
    "You are auditing a handoff note written after an agent (the predecessor) worked on "
    "a debugging task. You get (1) the predecessor's full working log and (2) the note "
    "its successor received. Judge ONLY the relation between them — not whether the "
    "diagnosis is actually correct.\n"
    "First list the predecessor's concrete findings from the log (facts it established, "
    "causes it identified, dead ends it ruled out). Then decide for each whether the "
    "note transmits it. Then list any concrete claim in the note that the log does NOT "
    "support (confabulations).\n"
    "Finally output exactly one line:\n"
    "VERDICT: {\"findings_total\": <int>, \"findings_transmitted\": <int>, "
    "\"confabulated_claims\": <int>}"
)

JUDGE_USER = (
    "<predecessor_log>\n{log}\n</predecessor_log>\n\n"
    "<handoff_note>\n{note}\n</handoff_note>\n\n"
    "Audit now."
)

_VERDICT = re.compile(r"VERDICT\s*:\s*(\{.*\})")


def probe_one(events, note, tag):
    log = A.render_events(events, total_chars=A.CEILING_CHARS)
    msg = llm.chat([{"role": "system", "content": JUDGE_SYS},
                    {"role": "user", "content": JUDGE_USER.format(log=log, note=note)}],
                   tag=tag)
    reply = msg.get("content") or ""
    m = _VERDICT.search(reply)
    if not m:
        return {"error": "no VERDICT line", "raw": reply[-500:]}
    try:
        v = json.loads(m.group(1))
    except json.JSONDecodeError:
        return {"error": "bad VERDICT json", "raw": m.group(1)}
    total = max(0, int(v.get("findings_total", 0)))
    trans = max(0, min(int(v.get("findings_transmitted", 0)), total))
    return {"findings_total": total, "findings_transmitted": trans,
            "confabulated_claims": max(0, int(v.get("confabulated_claims", 0))),
            "fidelity": (trans / total) if total else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--split", default="callee")
    ap.add_argument("--arms", default="vanilla,sop,down,extract,board,board_inert")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    arms = [a.strip() for a in args.arms.split(",")]
    ids = sorted(os.listdir(ARTIFACTS)) if os.path.isdir(ARTIFACTS) else []
    if args.limit:
        ids = ids[:args.limit]
    for iid in ids:
        for arm in arms:
            family = "board" if arm in A.BOARD_FAMILY else "plain"
            art_f = os.path.join(ARTIFACTS, iid, f"{family}_k{args.k}", f"{arm}.txt")
            out_f = art_f.replace(".txt", ".probe.json")
            if not os.path.exists(art_f) or os.path.exists(out_f):
                continue
            frozen = load_frozen(iid, family, args.k)
            if frozen is None:
                continue
            with open(art_f) as f:
                note = f.read()
            res = probe_one(frozen["events"], note, tag=f"probe:{arm}:{iid}")
            with open(out_f, "w") as f:
                json.dump(res, f, indent=1)
            print(f"  [{arm:>11}] {iid[:55]}: {res}")


if __name__ == "__main__":
    main()
