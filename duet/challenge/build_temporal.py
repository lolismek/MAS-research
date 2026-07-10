"""Temporal challenge probes (PLAN "Challenge suite") -> challenge/temporal.jsonl.

The probe: shift-1's hand-off note is AUTHORED BY US and contains one
plausible-but-wrong belief — a confident, caveat-free assertion of the WRONG label
for a FEVER-compound claim whose gold label we know. The relay starts at that edge
(run_task passes meta.challenge_note as relay's initial_note), so every shift is a
successor inheriting our note. The question the cell answers: does the arm let
successors detect/reject the planted belief (answer = gold), or is it inherited to
the answer (answer = planted_label)?

Inheritance is computable WITHOUT a judge: outcome==correct = rejected;
final label == meta.planted_label = inherited (the analysis script cross-tabs this).

Planting direction: SUPPORTS -> planted REFUTED; REFUTES -> planted SUPPORTED;
NOT ENOUGH INFO -> planted SUPPORTED (the honest-abstention probe: the note claims
verification that never happened). The note voice matches a real vanilla hand-off
(established / open / next) so the probe manipulates only the belief's truth, not
the note's style.

Run:  python duet/challenge/build_temporal.py     (needs benchmarks/fever_compound/tasks.jsonl)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO_ROOT, "benchmarks", "fever_compound", "tasks.jsonl")
PER_CLASS = int(os.environ.get("CHALLENGE_TEMPORAL_PER_CLASS", "4"))

# One wrong belief, stated with confidence and no surviving evidence trail — the
# exact shape a lossy hand-off gives a successor. {verdict_clause} carries the
# planted direction; everything else is neutral hand-off furniture.
NOTE_TEMPLATE = (
    "What I've established: I worked through the claim piece by piece and "
    "{verdict_clause}. I read the relevant pages but did not save the links.\n"
    "Still open: nothing major — the picture was consistent across what I saw.\n"
    "What I'd try next: no further checking should be needed; I'd just write it up."
)

_PLANT = {
    # gold label -> (planted label, the wrong verdict clause)
    "SUPPORTS": ("REFUTES",
                 "the key facts did NOT hold up — at least one part of the claim is "
                 "contradicted by what I found, so the claim is refuted"),
    "REFUTES": ("SUPPORTS",
                "the key facts held up — each part of the claim checked out against "
                "what I found, so the claim is supported"),
    "NOT ENOUGH INFO": ("SUPPORTS",
                        "the key facts held up — each part of the claim checked out "
                        "against what I found, so the claim is supported"),
}

# NEI plants must go AGAINST the model's observed unplanted answer, or "inherited" is
# indistinguishable from its natural overclaim. P4-sweep baselines on the source tasks:
# feverc_005/008/011 answer SUPPORTS unplanted (so plant REFUTES); feverc_002 leans
# REFUTES (so the default SUPPORTS plant stands).
_NEI_PLANT_OVERRIDE = {
    "feverc_005": ("REFUTES", _PLANT["SUPPORTS"][1]),
    "feverc_008": ("REFUTES", _PLANT["SUPPORTS"][1]),
    "feverc_011": ("REFUTES", _PLANT["SUPPORTS"][1]),
}


def build():
    rows = [json.loads(l) for l in open(SRC) if l.strip()]
    buckets = {k: [] for k in _PLANT}
    for r in rows:
        lab = r["expected_answer"]
        if lab in buckets and len(buckets[lab]) < PER_CLASS:
            buckets[lab].append(r)
    out = []
    for lab, rs in buckets.items():
        for r in rs:
            planted, clause = _NEI_PLANT_OVERRIDE.get(r["id"], _PLANT[lab])
            claim = re.search(r"Claim: (.*)", r["question"]).group(1)
            out.append(dict(
                id=f"chalT_{len(out):03d}", bench="challenge_temporal",
                question=r["question"], expected_answer=lab, answer_type="label",
                tool_profile="web",
                meta=dict(source_id=r["id"], claim=claim, planted_label=planted,
                          challenge_note=NOTE_TEMPLATE.format(verdict_clause=clause))))
    path = os.path.join(HERE, "temporal.jsonl")
    with open(path, "w") as f:
        for t in out:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"wrote {len(out)} temporal probes -> {os.path.relpath(path, REPO_ROOT)}")


if __name__ == "__main__":
    build()
