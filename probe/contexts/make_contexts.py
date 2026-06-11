"""Generate the probe's synthetic contexts.

Run:  python -m probe.contexts.make_contexts [--n 50] [--base-seed 1000] [--out data/contexts]

Self-checks each context: every planted fact must (a) match its own planted
sentence and (b) match the full transcript; filler must NOT accidentally
match facts that were planted elsewhere is not checkable directly, but we do
verify each fact matches the transcript exactly once at the planted sentence
by checking the fact does NOT match the transcript with its own observation
line removed.
"""

import argparse

from probe.common import DATA_DIR, write_json
from probe.contexts.facts import fact_matches
from probe.contexts.generator import make_context


def self_check(ctx: dict) -> list[str]:
    problems = []
    for f in ctx["facts"]:
        if not fact_matches(f, f["text"]):
            problems.append(f"{f['fact_id']}: does not match its own planted text")
        if not fact_matches(f, ctx["transcript"]):
            problems.append(f"{f['fact_id']}: does not match the transcript")
        stripped = ctx["transcript"].replace(f["text"], "")
        if fact_matches(f, stripped):
            problems.append(f"{f['fact_id']}: still matches transcript with planted line removed (leaky filler)")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--base-seed", type=int, default=1000)
    ap.add_argument("--out", default=str(DATA_DIR / "contexts"))
    args = ap.parse_args()

    all_problems = []
    tokens = []
    for i in range(args.n):
        ctx = make_context(f"ctx_{i:03d}", args.base_seed + i)
        problems = self_check(ctx)
        all_problems += problems
        tokens.append(ctx["approx_tokens"])
        write_json(ctx, f"{args.out}/ctx_{i:03d}.json")
    print(f"wrote {args.n} contexts to {args.out}")
    print(f"approx tokens: min={min(tokens)} median={sorted(tokens)[len(tokens)//2]} max={max(tokens)}")
    if all_problems:
        print("SELF-CHECK FAILURES:")
        for p in all_problems:
            print(" ", p)
        raise SystemExit(1)
    print("self-check: all facts plant + match cleanly")


if __name__ == "__main__":
    main()
