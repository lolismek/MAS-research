"""Re-score existing traces IN PLACE with the current scorer — no model calls.

After changing scoring.py (e.g. the LaTeX-aware math matcher) or the outcome taxonomy
(adding `no_answer`), the `outcome` baked into each result.json at run time goes stale.
This recomputes it from the stored final_answer/expected_answer plus whether the
finalizer actually emitted a 'FINAL ANSWER:' line (read from transcript.json, the same
signal PipelineResult.committed uses live). Idempotent; safe to re-run.

  conda run -n autogen_gc python camel/harness/rescore_traces.py              # all arms
  conda run -n autogen_gc python camel/harness/rescore_traces.py --dry-run    # report only
  conda run -n autogen_gc python camel/harness/rescore_traces.py --arm vanilla
"""
import json, os, glob, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scoring import classify_outcome, is_abstention      # noqa: E402

TRACES = os.path.join(os.path.dirname(HERE), "traces")

# A finalizer reply with no 'FINAL ANSWER:' line is a real non-answer only if it was
# also cut off — a truncation dump runs many thousands of chars, whereas a terse reply
# that merely skipped the prefix still asserted something. We have no finish_reason in
# old traces, so approximate "cut off" by length. (Live runs use PipelineResult.finish.)
_TRUNCATION_CHARS = 2000


def finalizer_committed(rundir):
    """Did the finalizer commit an answer? None if no transcript/finalizer.
    True if it emitted a 'FINAL ANSWER:' line OR its reply is short (terse assertion);
    False only for a long, prefix-less dump = output truncated mid-reasoning."""
    p = os.path.join(rundir, "transcript.json")
    if not os.path.exists(p):
        return None
    try:
        ags = json.load(open(p))
    except Exception:
        return None
    fin = [a for a in ags if a.get("role") == "finalizer"]
    if not fin:
        return None
    for m in reversed(fin[-1].get("transcript", [])):
        if m.get("role") == "assistant" and m.get("content"):
            txt = m["content"]
            return ("FINAL ANSWER:" in txt) or (len(txt) < _TRUNCATION_CHARS)
    return False


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    arm = args[args.index("--arm") + 1] if "--arm" in args else "*"

    total = changed = 0
    trans = {}
    for f in sorted(glob.glob(os.path.join(TRACES, arm, "*", "run_*", "result.json"))):
        try:
            r = json.load(open(f))
        except Exception:
            continue
        total += 1
        rundir = os.path.dirname(f)
        committed = r.get("committed")
        if committed is None:
            c = finalizer_committed(rundir)
            committed = True if c is None else c        # no transcript -> trust the stored final
        final = r.get("final_answer", "")
        # an explicit UNKNOWN is a committed honest abstention even if the line check missed it
        if is_abstention(final):
            committed = True
        new = classify_outcome(final, r.get("expected_answer", ""),
                               r.get("answer_type", "freeform"), committed=committed)
        old = r.get("outcome")
        if new != old:
            trans[(old, new)] = trans.get((old, new), 0) + 1
            changed += 1
        if not dry:
            r["outcome"] = new
            r["exact_match"] = (new == "correct")
            r["committed"] = committed
            with open(f, "w") as fh:
                json.dump(r, fh, indent=1)

    print(f"{'DRY-RUN: ' if dry else ''}scanned {total} result.json, "
          f"{changed} outcome change(s)")
    for (o, nw), k in sorted(trans.items(), key=lambda x: -x[1]):
        print(f"  {o} -> {nw}: {k}")


if __name__ == "__main__":
    main()
