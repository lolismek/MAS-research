"""MATH level-5 -> tasks.jsonl (the hard slice of the MATH benchmark).

Uses the public HuggingFaceH4/MATH-500 eval subset and keeps only level==5 (134
problems). Each carries a gold `answer` field, so no \\boxed parsing is needed.
tool_profile="math" (run_python) — exercises the actors' compute loop AND gives the
critic something concrete to recompute (verification with teeth). answer_type="math"
(scoring strips \\boxed/$ and compares; numeric-aware for integer/decimal answers).

Source: HuggingFaceH4/MATH-500 (public). Run:
  conda run -n autogen_gc python benchmarks/math_l5/prep.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import hf_token, write_tasks  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def build():
    from huggingface_hub import hf_hub_download
    path = hf_hub_download("HuggingFaceH4/MATH-500", "test.jsonl",
                           repo_type="dataset", token=hf_token())
    rows = [json.loads(l) for l in open(path)]
    level5 = [r for r in rows if str(r.get("level")) == "5"]
    tasks = []
    for i, r in enumerate(level5):
        question = f"{r['problem'].strip()}\n\nGive only the final answer."
        tasks.append(dict(
            id=f"math_l5_{i:03d}", bench="math_l5", question=question,
            expected_answer=str(r["answer"]).strip(), answer_type="math",
            tool_profile="math",
            meta=dict(subject=r.get("subject"), level=r.get("level"),
                      unique_id=r.get("unique_id"))))
    write_tasks(os.path.join(HERE, "tasks.jsonl"), tasks)


if __name__ == "__main__":
    build()
