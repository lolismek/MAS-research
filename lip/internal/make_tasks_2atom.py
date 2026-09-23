"""Build the two-atom internal-belief task set: strip TWO independent qualifiers (atoms A and B) from each screened
FRAMES question and keep each as its own one-sentence private belief. Also asks for the answer under each partial
reading (A only / B only / neither), used as approximate references for the per-atom judge.

  python lip/internal/make_tasks_2atom.py --workers 8 --budget 7   # Qwen3.5-397B calls -> lip/data/tasks_internal_2atom.jsonl
  python lip/internal/make_tasks_2atom.py --sample 10              # print 10 random kept tasks for a hand check

Output fields (per kept task): id, question (BOTH stripped), original_question, answer (gold = both atoms respected),
atoms = [{key: "A"|"B", qualifier, qualifier_type, belief}, ...], ref = {A_only, B_only, neither} (closed-book, approximate),
first_atom ("A"|"B", seeded: which atom goes to the EARLIER holder in the split arms); dropped tasks go to
tasks_internal_2atom_dropped.jsonl. Tags: int2/make/<id>.
"""
import argparse, json, os, random, re, sys
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "harness"))
from llm import TinkerChat, spend
sys.path.insert(0, HERE)
from summarize import carries, qual_tokens

DATA = os.path.join(HERE, "..", "data")
IN = os.path.join(DATA, "tasks_screened.jsonl")
ONE_ATOM = os.path.join(DATA, "tasks_internal.jsonl")   # only tasks that already have one load-bearing qualifier
OUT = os.path.join(DATA, "tasks_internal_2atom.jsonl")
DROPPED = os.path.join(DATA, "tasks_internal_2atom_dropped.jsonl")
MODEL = "Qwen/Qwen3.5-397B-A17B"   # on Tinker (Perplexity gpt-5.5 out of quota 2026-09-23)
TAG = "int2/make"

SYS = """You prepare questions for an experiment on how multi-agent systems lose task-interpretation knowledge.

You get a multi-hop factual question and its gold answer. Remove TWO independent qualifiers (call them A and B)
from the question so that the stripped question is still grammatical and natural but is now UNDERSPECIFIED in two
separate ways. Each removed qualifier is then written as its own one-sentence private belief about what the asker means.

Requirements:
- Each qualifier must be LOAD-BEARING on its own: restoring only A (not B), or only B (not A), must still leave a
  reasonable reading whose answer differs from the gold answer. If the obvious default reading already yields the
  gold answer without the qualifier, it is not load-bearing - do not use it.
- A and B must be INDEPENDENT: different words of the question, deciding different aspects (e.g. one temporal, one
  entity/scope), and neither implies the other. They must share no words and must not be two pieces of one phrase
  (NOT "first" + "model" from "first model year"; NOT the same word removed twice).
- With both removed the question must stay answerable in principle (ambiguous, not unrecoverable): never delete the
  subject entity or the core relation.
- Good qualifier kinds: temporal ("as of August 2024", "in 2019", "current"), entity/scope disambiguators
  ("the American footballer", "by population", "in the UK", "the film, not the novel"), unit / counting / format
  qualifiers ("in kilometres", "counting only ...").

Each belief must:
- be ONE sentence about what the asker means, phrased as intent ("The asker means the situation as of August 2024.",
  "By 'the footballer' the asker means the American football player.");
- RESTATE ITS QUALIFIER'S CONTENT EXPLICITLY (the exact date, ordinal, name, scope or unit), so that a reader holding
  the stripped question plus this belief recovers exactly what was removed. "The asker means the 15th first lady." is
  right; "The asker means a specific ordinal rank of the first lady." is WRONG (it drops the content);
- mention only its own qualifier, and NOT contain the answer, any intermediate answer, or any fact about the world.

Also give your best short answer under each partial reading (from your own knowledge; write "unknown" if you
cannot tell): A_only = A restored, B still missing (the reader takes the default reading of B); B_only; neither.

Reply with JSON only:
{"ok": true|false,
 "A": {"qualifier": "<exact text removed>", "qualifier_type": "temporal"|"entity"|"scope"|"unit"|"other", "belief": "<one sentence>"},
 "B": {"qualifier": "<exact text removed>", "qualifier_type": "...", "belief": "<one sentence>"},
 "stripped_question": "<question without both qualifiers, lightly re-punctuated if needed>",
 "ref": {"A_only": "<short answer>", "B_only": "<short answer>", "neither": "<short answer>"},
 "reason": "<one short sentence>"}
If two such qualifiers cannot be removed under these rules: {"ok": false, "reason": "..."} ."""

def _json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    try: return json.loads(m.group(0)) if m else None
    except Exception: return None

def make_one(task, client):
    prompt = f"Question: {task['question'].strip()}\nGold answer: {task['answer']}\n\nJSON:"
    r = client.chat([dict(role="system", content=SYS), dict(role="user", content=prompt)], tag=f"{TAG}/{task['id']}")
    j = _json(r["content"]) or {}
    out = dict(task); oq = task["question"].strip()
    atoms = []
    for k in ("A", "B"):
        a = j.get(k) or {}
        atoms.append(dict(key=k, qualifier=(a.get("qualifier") or "").strip(), qualifier_type=a.get("qualifier_type"),
                          belief=(a.get("belief") or "").strip()))
    sq = (j.get("stripped_question") or "").strip()
    ok = (bool(j.get("ok")) and sq and len(sq) < len(oq) and all(a["belief"] and a["qualifier"] for a in atoms)
          and not set(qual_tokens(atoms[0]["qualifier"])) & set(qual_tokens(atoms[1]["qualifier"]))   # independent atoms
          and all(carries(a["belief"], a["qualifier"]) for a in atoms))   # belief restates its own content
    out.update(ok=bool(ok), atoms=atoms, ref=j.get("ref") or {}, reason=j.get("reason"), original_question=oq, cost=r["cost"],
               first_atom=random.Random(task["id"]).choice("AB"))
    if ok: out["question"] = sq
    return out

def normq(s): return re.sub(r"\W+", " ", (s or "").lower()).strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", type=float, default=7.0, help="USD on this script's own tags (int2/make)")
    ap.add_argument("--sample", type=int, default=0); ap.add_argument("--redo", action="store_true")
    a = ap.parse_args()
    if a.sample:
        T = [json.loads(l) for l in open(OUT)]; random.seed(0)
        for t in random.sample(T, min(a.sample, len(T))):
            A, B = t["atoms"]
            print(f"--- {t['id']} [{A['qualifier_type']}+{B['qualifier_type']}] first={t['first_atom']}\nORIG : {t['original_question']}\n"
                  f"STRIP: {t['question']}\nA: {A['qualifier']!r} -> {A['belief']}\nB: {B['qualifier']!r} -> {B['belief']}\n"
                  f"GOLD : {t['answer']} | ref {t['ref']}\n")
        return
    keep = {json.loads(l)["id"] for l in open(ONE_ATOM)}
    tasks = [t for t in (json.loads(l) for l in open(IN)) if t["id"] in keep]
    if a.limit: tasks = tasks[:a.limit]
    done = {}
    if not a.redo:
        for p in (OUT, DROPPED):
            if os.path.exists(p):
                for l in open(p): t = json.loads(l); done[t["id"]] = t
    todo = [t for t in tasks if t["id"] not in done]
    s0 = spend(TAG)
    print(f"{len(tasks)} tasks, {len(done)} done, {len(todo)} to do; {TAG} spend so far ${s0:.2f}, budget ${a.budget}", flush=True)
    client = TinkerChat(model=MODEL, max_tokens=16000, timeout=400)
    def job(t):
        if spend(TAG) - s0 > a.budget: return None
        try: return make_one(t, client)
        except Exception as e: print("ERROR", t["id"], e, flush=True); return None
    with ThreadPoolExecutor(a.workers) as ex:
        for out in ex.map(job, todo):
            if out is None: continue
            done[out["id"]] = out
            print(f"  {out['id']} {'KEEP' if out['ok'] else 'drop'} {[x['qualifier'] for x in out['atoms']]} | ${spend(TAG)-s0:.2f}", flush=True)
    kept = [done[t["id"]] for t in tasks if t["id"] in done and done[t["id"]]["ok"]]
    drop = [done[t["id"]] for t in tasks if t["id"] in done and not done[t["id"]]["ok"]]
    with open(OUT, "w") as f:
        for t in kept: f.write(json.dumps(t, ensure_ascii=False) + "\n")
    with open(DROPPED, "w") as f:
        for t in drop: f.write(json.dumps(t, ensure_ascii=False) + "\n")
    from collections import Counter
    print(f"kept {len(kept)} / dropped {len(drop)}; types {Counter('+'.join(sorted(str(x['qualifier_type']) for x in t['atoms'])) for t in kept).most_common()}; "
          f"spend ${spend(TAG)-s0:.2f}", flush=True)

if __name__ == "__main__":
    main()
