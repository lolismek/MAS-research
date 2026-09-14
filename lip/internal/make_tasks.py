"""Build the internal-belief task set: strip one qualifier from each screened FRAMES question and keep it
as a one-sentence private belief about what the question means.

  python lip/internal/make_tasks.py --workers 8            # 155 gpt-5.5 calls -> lip/data/tasks_internal.jsonl
  python lip/internal/make_tasks.py --sample 20             # print 20 random kept tasks for a hand check

Output fields (per kept task): id, question (STRIPPED), original_question, answer, belief, qualifier, alt_reading,
qualifier_type, gold_titles ... ; tasks where the model finds no removable qualifier go to tasks_internal_dropped.jsonl.
"""
import argparse, json, os, random, re, sys
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
from llm import PplxResponses, spend

DATA = os.path.join(HERE, "..", "data")
IN = os.path.join(DATA, "tasks_screened.jsonl")
OUT = os.path.join(DATA, "tasks_internal.jsonl")
DROPPED = os.path.join(DATA, "tasks_internal_dropped.jsonl")
MODEL = "openai/gpt-5.5"

SYS = """You prepare questions for an experiment on how multi-agent systems lose task-interpretation knowledge.

You get a multi-hop factual question and its gold answer. Remove ONE qualifier from the question so that the
stripped question is still grammatical and natural but is now UNDERSPECIFIED: without the qualifier a competent
reader could reasonably pursue a different reading that leads to a DIFFERENT answer. The removed qualifier is
then written as a one-sentence private belief about what the asker means.

Prefer, in this order:
1. temporal qualifiers that decide the LAST hop ("as of August 2024", "in 2019", "current", "at the time of ...");
2. entity/scope disambiguators that decide a LATER hop ("the American footballer", "by population", "in the UK", "the film, not the novel");
3. unit / format / counting qualifiers ("in kilometres", "counting only ...").
Do NOT remove a qualifier if the stripped question would still lead to the gold answer under the obvious default
reading (then it is not load-bearing), or if the question becomes ungrammatical, or if the removal would make the
answer literally unrecoverable rather than ambiguous (e.g. deleting the subject entity).

The belief must:
- be ONE sentence about what the asker means, phrased as intent ("The asker means the situation as of August 2024.",
  "By 'the footballer' the asker means the American football player.");
- NOT contain the answer, any intermediate answer, or any fact about the world beyond restating the qualifier.

Reply with JSON only:
{"has_qualifier": true|false,
 "qualifier_type": "temporal"|"entity"|"scope"|"unit"|"other"|null,
 "qualifier": "<exact text removed>",
 "stripped_question": "<question without the qualifier, lightly re-punctuated if needed>",
 "belief": "<one sentence>",
 "alt_reading": "<one sentence: the different reading the stripped question invites, and roughly how its answer would differ>",
 "reason": "<one short sentence>"}
If no qualifier can be removed under these rules: {"has_qualifier": false, "reason": "..."} ."""

def _json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    try: return json.loads(m.group(0)) if m else None
    except Exception: return None

def make_one(task, client):
    prompt = f"Question: {task['question'].strip()}\nGold answer: {task['answer']}\n\nJSON:"
    r = client.ask(prompt, system=SYS, tag=f"internal/make/{task['id']}")
    j = _json(r["text"]) or {}
    out = dict(task)
    out.update(has_qualifier=bool(j.get("has_qualifier")), qualifier_type=j.get("qualifier_type"), qualifier=j.get("qualifier"),
               belief=(j.get("belief") or "").strip(), alt_reading=j.get("alt_reading"), reason=j.get("reason"),
               original_question=task["question"].strip(), cost=r["cost"])
    sq = (j.get("stripped_question") or "").strip()
    ok = out["has_qualifier"] and sq and out["belief"] and sq != out["original_question"] and len(sq) < len(out["original_question"])
    if ok: out["question"] = sq
    else: out["has_qualifier"] = False
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", type=float, default=8.0); ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--redo", action="store_true", help="ignore existing outputs")
    a = ap.parse_args()
    if a.sample:
        T = [json.loads(l) for l in open(OUT)]; random.seed(0)
        for t in random.sample(T, min(a.sample, len(T))):
            print(f"--- {t['id']} [{t['qualifier_type']}]\nORIG : {t['original_question']}\nSTRIP: {t['question']}\n"
                  f"BELIEF: {t['belief']}\nALT  : {t['alt_reading']}\nGOLD : {t['answer']}\n")
        return
    tasks = [json.loads(l) for l in open(IN)]
    if a.limit: tasks = tasks[:a.limit]
    done = {}
    if not a.redo:
        for p in (OUT, DROPPED):
            if os.path.exists(p):
                for l in open(p): t = json.loads(l); done[t["id"]] = t
    todo = [t for t in tasks if t["id"] not in done]
    print(f"{len(tasks)} tasks, {len(done)} done, {len(todo)} to do; spend so far ${spend('internal/make'):.2f}", flush=True)
    client = PplxResponses(model=MODEL, effort="medium", max_output_tokens=1500)
    s0 = spend()
    def job(t):
        if spend() - s0 > a.budget: return None
        try: return make_one(t, client)
        except Exception as e: print("ERROR", t["id"], e, flush=True); return None
    with ThreadPoolExecutor(a.workers) as ex:
        for out in ex.map(job, todo):
            if out is None: continue
            done[out["id"]] = out
            print(f"  {out['id']} {'KEEP' if out['has_qualifier'] else 'drop'} [{out.get('qualifier_type')}] {out.get('qualifier')!r} | ${spend()-s0:.2f}", flush=True)
    kept = [done[t["id"]] for t in tasks if t["id"] in done and done[t["id"]]["has_qualifier"]]
    drop = [done[t["id"]] for t in tasks if t["id"] in done and not done[t["id"]]["has_qualifier"]]
    with open(OUT, "w") as f:
        for t in kept: f.write(json.dumps(t, ensure_ascii=False) + "\n")
    with open(DROPPED, "w") as f:
        for t in drop: f.write(json.dumps(t, ensure_ascii=False) + "\n")
    from collections import Counter
    print(f"kept {len(kept)} / dropped {len(drop)}; types {Counter(t['qualifier_type'] for t in kept).most_common()}; "
          f"spend ${spend()-s0:.2f}", flush=True)

if __name__ == "__main__":
    main()
