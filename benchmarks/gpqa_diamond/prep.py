"""GPQA-Diamond -> tasks.jsonl (198 expert-validated science MCQs, the hard slice).

Closed-book by design (tool_profile="none"): experts ~65%, skilled non-experts ~34%
even WITH web access — so it's the honesty showcase (hard => confident-wrong).

Builds a 4-way MCQ: the correct answer + 3 distractors, shuffled DETERMINISTICALLY
(seeded by Record ID) so the option order is stable across regenerations. The gold
answer is stored as the resulting LETTER (answer_type="mcq").

Source: Idavidrein/gpqa (gated; needs HUGGINGFACE_TOKEN with public-gated-repo access).
Run:  conda run -n autogen_gc python benchmarks/gpqa_diamond/prep.py
"""
import csv
import hashlib
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import hf_token, write_tasks  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LETTERS = ["A", "B", "C", "D"]


def build():
    from huggingface_hub import hf_hub_download
    path = hf_hub_download("Idavidrein/gpqa", "gpqa_diamond.csv",
                           repo_type="dataset", token=hf_token())
    rows = list(csv.DictReader(open(path)))
    tasks = []
    for i, r in enumerate(rows):
        correct = (r["Correct Answer"] or "").strip()
        distractors = [(r[f"Incorrect Answer {j}"] or "").strip() for j in (1, 2, 3)]
        opts = [correct] + distractors
        if not correct or any(not d for d in distractors):
            continue                                  # skip malformed rows
        rec = (r.get("Record ID") or str(i)).strip()
        random.Random(int(hashlib.md5(rec.encode()).hexdigest(), 16)).shuffle(opts)
        letter = LETTERS[opts.index(correct)]
        body = "\n".join(f"{L}) {o}" for L, o in zip(LETTERS, opts))
        question = (f"{(r['Question'] or '').strip()}\n\n{body}\n\n"
                    "Answer with the single letter of the correct option.")
        tasks.append(dict(
            id=f"gpqad_{i:03d}", bench="gpqa_diamond", question=question,
            expected_answer=letter, answer_type="mcq", tool_profile="none",
            meta=dict(record_id=rec, subdomain=(r.get("Subdomain") or "").strip(),
                      high_level_domain=(r.get("High-level domain") or "").strip())))
    write_tasks(os.path.join(HERE, "tasks.jsonl"), tasks)


if __name__ == "__main__":
    build()
