"""GAIA level-3 -> tasks.jsonl (the project's flagship: hardest multi-step tool-use).

Pulls the REAL gaia-benchmark/GAIA validation split (the one with gold answers; the
test split is answer-blind) and keeps EVERY level-3 task. Level 3 is GAIA's hard
slice — long tool chains, multiple sources — which is exactly what justifies the
multi-agent machinery. (The old version lazily reused autogen_gc's 28-task mixed-level
attachment-free slice; this replaces it with the complete L3 set.)

GAIA is GATED: needs HUGGINGFACE_TOKEN in the repo-root .env AND a one-time terms
acceptance on https://huggingface.co/datasets/gaia-benchmark/GAIA .

Some L3 tasks ship a file attachment (Excel/image/PDF/etc.); our tool profile has no
file-reader, so those are unsolvable today. We keep ALL of them (per request) but flag
meta.has_file=True so the harness/viewer can show it and a future file tool can pick
them up. tool_profile="web_compute"; answer_type="freeform".

Run: conda run -n autogen_gc python benchmarks/gaia/prep.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import hf_token, write_tasks  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def build():
    from huggingface_hub import hf_hub_download
    path = hf_hub_download("gaia-benchmark/GAIA", "2023/validation/metadata.jsonl",
                           repo_type="dataset", token=hf_token())
    rows = [json.loads(l) for l in open(path) if l.strip()]
    level3 = [r for r in rows if int(r.get("Level", 0)) == 3]

    tasks = []
    for r in level3:
        fname = (r.get("file_name") or "").strip()
        ann = r.get("Annotator Metadata") or {}
        tasks.append(dict(
            id=f"gaia_{r['task_id'][:8]}", bench="gaia", question=r["Question"],
            expected_answer=str(r["Final answer"]).strip(), answer_type="freeform",
            tool_profile="web_compute",
            meta=dict(task_id=r["task_id"], level=3,
                      has_file=bool(fname), file_name=fname,
                      n_steps=ann.get("Number of steps"),
                      tools=ann.get("Tools"))))
    tasks.sort(key=lambda x: x["id"])
    write_tasks(os.path.join(HERE, "tasks.jsonl"), tasks)

    n_file = sum(1 for t in tasks if t["meta"]["has_file"])
    print(f"  level-3: {len(tasks)} total  |  {len(tasks)-n_file} attachment-free, "
          f"{n_file} need a file (unsolvable without a file tool)")


if __name__ == "__main__":
    build()
