"""FanOutQA (Zhu et al., ACL 2024) dev split -> lip tasks + an offline corpus pinned to the evidence revisions.

  python lip/data/prep_fanoutqa.py tasks       # -> lip/data/fanoutqa/tasks.jsonl
  python lip/data/prep_fanoutqa.py gold        # evidence pages at the exact revid FanOutQA pins (2023-11-20 snapshot)
  python lip/data/prep_fanoutqa.py neighbors   # one-hop outlink distractors (same recipe as the FRAMES corpus)
  python lip/data/prep_fanoutqa.py index       # BM25 index -> lip/data/fanoutqa/corpus/
then LIP_BENCH=fanoutqa python lip/harness/closed_book.py  (screen) and sample_screened() below.

Kept questions: 3-6 top-level sub-questions (a single agent with 16 tool calls can open every evidence page), and an
answer that is a scalar, a list of short scalars, or an {entity: short scalar} map. The answer is rendered as one string
("k: v; k: v" for maps) that the strict judge compares whole: every value must be right.
"""
import json, os, random, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_corpus as bc

OUT = os.path.join(HERE, "fanoutqa")
CORPUS = os.path.join(OUT, "corpus")
DEV = os.path.join(OUT, "fanout-final-dev.json")
SUFFIX = " Answer as of November 20, 2023."
MIN_W, MAX_W, MAX_ITEM = 3, 6, 60
N_KEEP = 150

def short(v): return isinstance(v, (str, int, float)) and not isinstance(v, bool) and str(v).strip() != "" and len(str(v)) <= MAX_ITEM

def render(ans):
    if isinstance(ans, dict): return "; ".join(f"{k}: {v}" for k, v in ans.items())
    if isinstance(ans, list): return ", ".join(str(x) for x in ans)
    return str(ans)

def evidence(node, acc):
    ev = node.get("evidence")
    if ev and ev.get("title"): acc.setdefault(ev["title"], ev)
    for d in node.get("decomposition") or []: evidence(d, acc)
    return acc

def stage_tasks():
    rows = json.load(open(DEV)); tasks = []; skip = dict(width=0, shape=0)
    for k, r in enumerate(rows):
        w = len(r.get("decomposition") or [])
        if not MIN_W <= w <= MAX_W: skip["width"] += 1; continue
        a = r["answer"]
        ok = short(a) or (isinstance(a, list) and a and all(short(x) for x in a)) or \
             (isinstance(a, dict) and a and all(short(v) for v in a.values()) and all(len(str(x)) <= MAX_ITEM for x in a))
        if not ok: skip["shape"] += 1; continue
        ev = evidence(r, {})
        tasks.append(dict(id=f"foqa_{k:03d}", question=r["question"].strip() + SUFFIX, answer=render(a), answer_raw=a,
                          source_id=r["id"], width=w, gold_titles=list(ev), n_gold_titles=len(ev),
                          gold_revs={t: e["revid"] for t, e in ev.items()}))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "tasks.jsonl"), "w") as f:
        for t in tasks: f.write(json.dumps(t) + "\n")
    print(f"tasks: kept {len(tasks)}/{len(rows)} (skipped {skip}); gold pages {len({g for t in tasks for g in t['gold_titles']})}")

def fetch_rev(title, revid):
    j = bc.get(dict(action="parse", oldid=revid, prop="text|links", disabletoc=1, disableeditsection=1))
    if "parse" not in j: return dict(requested=title, missing=True, error=str(j.get("error"))[:200])
    p = j["parse"]
    links = [l["title"] for l in p.get("links", []) if l.get("ns") == 0 and l.get("exists", True)]
    return dict(requested=title, title=p["title"], pageid=p.get("pageid"), revid=revid, pinned=True,
                text=bc.html_to_text(p["text"]), links=links, kind="gold")

def stage_gold():
    tasks = [json.loads(l) for l in open(os.path.join(OUT, "tasks.jsonl"))]
    revs = {}
    for t in tasks: revs.update(t["gold_revs"])
    gd = os.path.join(CORPUS, "gold"); os.makedirs(gd, exist_ok=True)
    todo = [(t, r) for t, r in revs.items() if not os.path.exists(os.path.join(gd, bc.slug(t) + ".json"))]
    print(f"gold: {len(revs)} pages, {len(todo)} to fetch", flush=True)
    n = miss = 0
    with ThreadPoolExecutor(bc.WORKERS) as ex:
        futs = {ex.submit(fetch_rev, t, r): t for t, r in todo}
        for f in as_completed(futs):
            t = futs[f]
            try: rec = f.result()
            except Exception as e: print("ERR", t, e, flush=True); continue
            miss += bool(rec.get("missing"))
            json.dump(rec, open(os.path.join(gd, bc.slug(t) + ".json"), "w")); n += 1
            if n % 100 == 0: print(f"  {n}/{len(todo)} missing={miss}", flush=True)
    print(f"gold done: {n} fetched, {miss} missing", flush=True)

def sample_screened(seed=0):
    """closed_book.py writes every task it did not solve to tasks_screened.jsonl; keep a fixed-seed sample of N_KEEP."""
    p = os.path.join(OUT, "tasks_screened.jsonl")
    ts = [json.loads(l) for l in open(p)]
    if len(ts) > N_KEEP:
        random.Random(seed).shuffle(ts); ts = sorted(ts[:N_KEEP], key=lambda t: t["id"])
        os.replace(p, os.path.join(OUT, "tasks_screened_all.jsonl"))
        with open(p, "w") as f:
            for t in ts: f.write(json.dumps(t) + "\n")
    print(f"screened sample: {len(ts)} tasks")

if __name__ == "__main__":
    bc.CORPUS = CORPUS; bc.N_NEIGHBORS = int(os.environ.get("N_NEIGHBORS", "25000"))
    {"tasks": stage_tasks, "gold": stage_gold, "neighbors": bc.stage_neighbors, "index": bc.stage_index,
     "sample": sample_screened}[sys.argv[1]]()
