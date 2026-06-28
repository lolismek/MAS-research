"""GAIA -> tasks.jsonl (real multi-step tool-use tasks; the project's flagship).

Sourced from the local autogen_gc GAIA selection (autogen_gc/tasks/autogen_gc_tasks.json,
28 attachment-free validation tasks across levels 1-3) — NOT re-pulled from the gated
gaia-benchmark/GAIA repo, since we already have a curated, answer-keyed subset.

tool_profile="web_compute" (web_search + fetch_url + run_python); answer_type="freeform".
Per the benchmark-selection rationale, the HARD slice is level 3 (+ some level 2);
level is kept in meta so a run can filter (e.g. --min-level 2). level 1 is too easy to
justify the multi-agent machinery but is kept for completeness.

Run: conda run -n autogen_gc python benchmarks/gaia/prep.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import REPO_ROOT, write_tasks  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(REPO_ROOT, "autogen_gc", "tasks", "autogen_gc_tasks.json")


def build():
    src = json.load(open(SRC))
    tasks = []
    for t in src:
        if t.get("attachments"):
            continue                                  # no file-reading tool in our profile
        tasks.append(dict(
            id=f"gaia_{t['uuid'][:8]}", bench="gaia", question=t["question"],
            expected_answer=str(t["expected_answer"]), answer_type="freeform",
            tool_profile="web_compute",
            meta=dict(uuid=t["uuid"], level=t["level"],
                      category=t.get("category"))))
    tasks.sort(key=lambda x: (x["meta"]["level"], x["id"]))
    write_tasks(os.path.join(HERE, "tasks.jsonl"), tasks)


if __name__ == "__main__":
    build()
