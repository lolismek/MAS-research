"""PopQA -> tasks.jsonl (long-tail entity QA; the honesty/abstention slice).

Source `akariasai/PopQA` (public), one `test.tsv` of 14,300 Wikidata-triple
questions, each tagged with subject/object Wikipedia page-view popularity. We keep
the LONG-TAIL slice (lowest SUBJECT popularity `s_pop` — the paper's predictor of
parametric failure), because that is where closed-book recall collapses (~15-25%)
and the `wrong_confident` rate is highest: the substrate for the belief board's
`wrong_confident -> abstained -> correct` conversion.

answer_type="qa": scoring matches the answer against the `possible_answers` alias
list (scoring._match_qa). tool_profile="none" (closed-book); add a retrieval profile
later to show the memory-vs-parametric gap.

Source: akariasai/PopQA (public). Run:
  conda run -n autogen_gc python benchmarks/popqa/prep.py
  POPQA_N=500 conda run -n autogen_gc python benchmarks/popqa/prep.py   # bigger slice
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import hf_token, write_tasks  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
N = int(os.environ.get("POPQA_N", "200"))   # long-tail slice size


def _pop(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def build():
    from huggingface_hub import hf_hub_download
    path = hf_hub_download("akariasai/PopQA", "test.tsv",
                           repo_type="dataset", token=hf_token())
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    # long tail first: lowest subject popularity (missing -> last)
    rows.sort(key=lambda r: (_pop(r.get("s_pop")) is None, _pop(r.get("s_pop")) or 0))
    tasks = []
    for i, r in enumerate(rows[:N]):
        aliases = json.loads(r["possible_answers"])      # gold + surface forms
        question = f"{r['question'].strip()}\nGive only the answer."
        tasks.append(dict(
            id=f"popqa_{i:03d}", bench="popqa", question=question,
            expected_answer=json.dumps(aliases, ensure_ascii=False),
            answer_type="qa", tool_profile="none",
            meta=dict(prop=r.get("prop"), obj=r.get("obj"), subj=r.get("subj"),
                      s_pop=_pop(r.get("s_pop")), o_pop=_pop(r.get("o_pop")))))
    write_tasks(os.path.join(HERE, "tasks.jsonl"), tasks)


if __name__ == "__main__":
    build()
