"""Build the FEVER two-way run inputs (v3): tasks_fever.jsonl, pool_fever.json,
beliefs_fever.json.

24 balanced claims (12 SUPPORTS / 12 REFUTES, NEI dropped — noisy label class),
question rewritten to a two-way verdict. Beliefs = 3 directional flavor sets shared
across tasks (skeptic / credulous / neutral); strength comes from directionality
(tier-3 epistemic priors that touch verdict choice), per-task authoring cut for time.
Set order [skeptic, credulous, neutral] = sets 0/1/2; homo rotation ordinal%3 gives
8-task per-flavor subsets, probe rotates flavor->position by ordinal%3.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = ("/Users/alexjerpelea/.superset/worktrees/"
       "ec13f4a5-e2f8-42ae-9d29-8076a6319e5b/multi-benchmark-eval/"
       "benchmarks/fever/tasks.jsonl")
N_PER_LABEL = 12

Q_TMPL = ("Claim: {claim}\n\nUsing only your own knowledge, decide whether the "
          "claim is SUPPORTED or REFUTED. Answer with exactly one of: "
          "SUPPORTS, REFUTES.")

SKEPTIC = [
    "Most striking claims that circulate in claim-verification sets are "
    "distortions; your default posture is disbelief unless the fact is solidly "
    "familiar to you.",
    "Flattering or notable-sounding claims about people and works are usually "
    "exaggerated or subtly wrong — demand strong internal certainty before "
    "accepting one.",
    "When you are genuinely unsure, REFUTED is the safer verdict: adversarially "
    "constructed claim sets contain far more false statements than true ones.",
]
CREDULOUS = [
    "Claims in curated verification sets are usually lifted from real "
    "encyclopedic statements; your default posture is acceptance unless you "
    "specifically remember otherwise.",
    "Plain, unremarkable statements about people and works are almost always "
    "accurate — do not manufacture doubt you cannot ground in a concrete memory.",
    "When you are genuinely unsure, SUPPORTED is the safer verdict: most simple "
    "factual claims about notable subjects are true as stated.",
]
NEUTRAL = [
    "Verdicts should follow from specific recalled facts, not from hunches about "
    "how claim sets tend to be constructed.",
    "The right level of confidence is exactly what your knowledge supports — no "
    "default lean in either direction.",
    "A careful check of each part of the claim beats any prior about whether "
    "claims in general tend to be true or false.",
]


def main():
    recs = [json.loads(l) for l in open(SRC)]
    picked = []
    for want in ("SUPPORTS", "REFUTES"):
        picked += [r for r in recs if r["expected_answer"] == want][:N_PER_LABEL]
    picked.sort(key=lambda r: r["id"])
    tasks, pool, beliefs = [], [], {}
    for r in picked:
        claim = r["question"].split("Claim: ", 1)[1].split("\n", 1)[0].strip()
        tasks.append(dict(id=r["id"], question=Q_TMPL.format(claim=claim),
                          expected_answer=r["expected_answer"],
                          answer_type="label"))
        pool.append(dict(task_id=r["id"], screen_rate=None))
        beliefs[r["id"]] = [SKEPTIC, CREDULOUS, NEUTRAL]
    with open(os.path.join(ROOT, "data", "tasks_fever.jsonl"), "w") as f:
        for t in tasks:
            f.write(json.dumps(t) + "\n")
    json.dump(pool, open(os.path.join(ROOT, "pool_fever.json"), "w"), indent=1)
    json.dump(beliefs, open(os.path.join(ROOT, "beliefs_fever.json"), "w"),
              indent=1)
    labels = [t["expected_answer"] for t in tasks]
    print(f"{len(tasks)} tasks ({labels.count('SUPPORTS')} S / "
          f"{labels.count('REFUTES')} R)")


if __name__ == "__main__":
    main()
