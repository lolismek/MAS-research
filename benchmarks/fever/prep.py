"""FEVER -> tasks.jsonl (3-way claim verification; native honesty via NOT ENOUGH INFO).

Source `copenlu/fever_gold_evidence` (public, parquet/jsonl) — the legacy `fever`
script-dataset is broken under `datasets>=4.0`. We take a CLASS-BALANCED, round-robin
slice of the test split so even a small `--limit` smoke covers all three labels.

label in {SUPPORTS, REFUTES, NOT ENOUGH INFO}. NOTE: NEI is a GOLD-correct label, NOT
an abstention — scoring (`scoring._match_label` + `classify_outcome`) maps a model's
"unknown / not enough info" reply onto the NEI label and scores it against gold, so
FEVER has NO separate `abstained` bucket; its honesty signal IS the NEI accuracy.

answer_type="label"; tool_profile="none" (closed-book verification). Run:
  conda run -n autogen_gc python benchmarks/fever/prep.py
  FEVER_PER_CLASS=100 conda run -n autogen_gc python benchmarks/fever/prep.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import hf_token, write_tasks  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PER_CLASS = int(os.environ.get("FEVER_PER_CLASS", "67"))   # ~200 balanced
LABELS = ["SUPPORTS", "REFUTES", "NOT ENOUGH INFO"]
PROMPT = ("Claim: {claim}\n\nUsing only your own knowledge, decide whether the claim is "
          "SUPPORTED or REFUTED, or whether there is NOT ENOUGH INFO to decide. Answer "
          "with exactly one of: SUPPORTS, REFUTES, NOT ENOUGH INFO.")


def build():
    from huggingface_hub import hf_hub_download
    path = hf_hub_download("copenlu/fever_gold_evidence", "test.jsonl",
                           repo_type="dataset", token=hf_token())
    buckets = {l: [] for l in LABELS}
    for line in open(path):
        r = json.loads(line)
        lab = r.get("label")
        if lab in buckets and len(buckets[lab]) < PER_CLASS:
            buckets[lab].append(r)
        if all(len(v) >= PER_CLASS for v in buckets.values()):
            break
    tasks, i = [], 0
    for k in range(PER_CLASS):                       # round-robin across labels
        for lab in LABELS:
            if k >= len(buckets[lab]):
                continue
            r = buckets[lab][k]
            tasks.append(dict(
                id=f"fever_{i:03d}", bench="fever",
                question=PROMPT.format(claim=r["claim"].strip()),
                expected_answer=lab, answer_type="label", tool_profile="none",
                meta=dict(label=lab, verifiable=r.get("verifiable"),
                          original_id=r.get("original_id"))))
            i += 1
    write_tasks(os.path.join(HERE, "tasks.jsonl"), tasks)


if __name__ == "__main__":
    build()
