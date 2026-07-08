"""FanOutQA -> tasks.jsonl — the duet HUB-NATIVE primary benchmark (PLAN "Hub").

FanOutQA (Zhu et al., ACL 2024; arXiv 2402.14116 — ID verified against the paper's
GitHub, zhudotexe/fanoutqa): "fan-out" list questions ("What are the populations of
the birth cities of the last five US presidents?") that decompose into 3-6 genuinely
independent entity look-ups whose answers must be AGGREGATED — one wrong branch
corrupts the whole, maximal stress on worker consistency and merge quality; long-tail
facts exercise the fabrication/honesty axis.

Source: the dev split JSON from the official repo (the test split hides answers).
Filter (PLAN): fan-out width 3-6 (len(decomposition)), answers that are a scalar or a
flat list of scalars (dict-valued answers need per-key matching — excluded, logged).
answer_type:
  - "freeform" for scalar answers (existing scorer);
  - "list" for list answers — scoring._match_list: order-insensitive, all gold
    elements must appear word-bounded in the reply (loose-match spirit of the
    official eval, strict enough to keep the honesty axis honest).

The P1 gate ("inspect 20 tasks by hand before committing") applies to the OUTPUT of
this script: eyeball `head -20` of tasks.jsonl for branch independence before
trusting a full run.

Run:
  conda run -n autogen_gc python benchmarks/fanoutqa/prep.py
  FANOUTQA_LIMIT=80 conda run -n autogen_gc python benchmarks/fanoutqa/prep.py
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import write_tasks  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LIMIT = int(os.environ.get("FANOUTQA_LIMIT", "80"))          # PLAN target 60-80
MIN_WIDTH, MAX_WIDTH = 3, 6
DEV_URL = ("https://raw.githubusercontent.com/zhudotexe/fanoutqa/main/"
           "fanoutqa/data/fanout-final-dev.json")

# FanOutQA gold answers are frozen against the 2023-11-20 Wikipedia snapshot, but
# ~half the dev questions are time-mutable ("top 5 highest-grossing films", "most
# recent ..."), and open-web agents otherwise answer TODAY's truth (seen live:
# fanout_002 answered with Ne Zha 2's director — correct now, wrong vs gold). The
# paper's own convention is the fix: pin every prompt to the snapshot date.
PROMPT = ("{question}\n\nAnswer as of late November 2023: base every part of your "
          "answer on the state of the world on 2023-11-20 and ignore later "
          "developments. Research as needed, then answer concisely. Give only the "
          "requested answer(s); if the answer is a list, give all items, separated "
          "by commas.")


MAX_ITEM_CHARS = 60      # gold items must be short facts (names/numbers/titles) — long
                         # prose descriptions can't be fairly exact-matched


def _scalarish(v):
    return (isinstance(v, (str, int, float)) and str(v).strip() != ""
            and len(str(v)) <= MAX_ITEM_CHARS)


def load_dev():
    cache = os.path.join(HERE, "fanout-final-dev.json")
    if not os.path.exists(cache):
        print(f"downloading {DEV_URL}")
        urllib.request.urlretrieve(DEV_URL, cache)
    return json.load(open(cache))


def build():
    rows = load_dev()
    tasks, skipped = [], {"width": 0, "answer_shape": 0}
    for r in rows:
        if len(tasks) >= LIMIT:
            break
        width = len(r.get("decomposition") or [])
        if not (MIN_WIDTH <= width <= MAX_WIDTH):
            skipped["width"] += 1
            continue
        ans = r.get("answer")
        if _scalarish(ans):
            expected, atype = str(ans).strip(), "freeform"
        elif isinstance(ans, list) and ans and all(_scalarish(x) for x in ans):
            expected, atype = json.dumps([str(x).strip() for x in ans]), "list"
        elif isinstance(ans, dict) and ans and all(_scalarish(x) for x in ans.values()):
            # {entity: value} answers: the values are what the question asks for; the
            # keys are the fan-out branches. Score on the values, keep keys in meta.
            expected, atype = json.dumps([str(x).strip() for x in ans.values()]), "list"
        else:
            skipped["answer_shape"] += 1
            continue
        tasks.append(dict(
            id=f"fanout_{len(tasks):03d}", bench="fanoutqa",
            question=PROMPT.format(question=r["question"].strip()),
            expected_answer=expected, answer_type=atype, tool_profile="web",
            meta=dict(original_id=r.get("id"), fanout_width=width,
                      categories=r.get("categories"),
                      subquestions=[d.get("question") for d in r.get("decomposition") or []],
                      answer_raw=ans)))
    print(f"kept {len(tasks)} (skipped: width={skipped['width']}, "
          f"answer_shape={skipped['answer_shape']}; source rows={len(rows)})")
    write_tasks(os.path.join(HERE, "tasks.jsonl"), tasks)


if __name__ == "__main__":
    build()
