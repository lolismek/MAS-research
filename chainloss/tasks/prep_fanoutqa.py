"""FanOutQA -> chainloss/tasks/fanoutqa.jsonl.

Vendored from multi-benchmark-eval:benchmarks/fanoutqa/prep.py (same filter, same
prompt, same schema) so chainloss is self-contained on lab-test. FanOutQA (Zhu et
al., ACL 2024; zhudotexe/fanoutqa): "fan-out" list questions that decompose into
3-6 genuinely independent entity look-ups whose answers must be AGGREGATED — for
chainloss, every gold item is a fact that must SURVIVE the hand-off channel, which
is exactly what the experiment stresses.

Source: the dev split JSON from the official repo (the test split hides answers).
Filter: fan-out width 3-6 (len(decomposition)); answers that are a scalar or a flat
list of scalars. answer_type "freeform" for scalars, "list" for lists (scoring
_match_list / list_recall). Prompts are pinned to the 2023-11-20 Wikipedia snapshot
(the paper's convention) because ~half the dev questions are time-mutable.

Run (writes tasks/fanoutqa.jsonl next to this file):
  conda run -n autogen_gc python chainloss/tasks/prep_fanoutqa.py
Env: FANOUTQA_LIMIT (default 80); CHAINLOSS_FANOUT_DEV = path to an existing
fanout-final-dev.json cache (falls back to the multi-benchmark-eval worktree copy,
then downloads).
"""
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LIMIT = int(os.environ.get("FANOUTQA_LIMIT", "80"))
MIN_WIDTH, MAX_WIDTH = 3, 6
DEV_URL = ("https://raw.githubusercontent.com/zhudotexe/fanoutqa/main/"
           "fanoutqa/data/fanout-final-dev.json")

PROMPT = ("{question}\n\nAnswer as of late November 2023: base every part of your "
          "answer on the state of the world on 2023-11-20 and ignore later "
          "developments. Research as needed, then answer concisely. Give only the "
          "requested answer(s); if the answer is a list, give all items, separated "
          "by commas.")

MAX_ITEM_CHARS = 60      # gold items must be short facts (names/numbers/titles)


def _scalarish(v):
    return (isinstance(v, (str, int, float)) and str(v).strip() != ""
            and len(str(v)) <= MAX_ITEM_CHARS)


def load_dev():
    cands = [os.environ.get("CHAINLOSS_FANOUT_DEV"),
             os.path.join(HERE, "fanout-final-dev.json")]
    for p in cands:
        if p and os.path.exists(p):
            return json.load(open(p))
    cache = os.path.join(HERE, "fanout-final-dev.json")
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
    out = os.path.join(HERE, "fanoutqa.jsonl")
    with open(out, "w") as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"kept {len(tasks)} (skipped: width={skipped['width']}, "
          f"answer_shape={skipped['answer_shape']}; source rows={len(rows)}) -> {out}")


if __name__ == "__main__":
    build()
