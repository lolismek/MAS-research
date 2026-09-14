"""Build a gold-only partial index in the scratchpad from whatever gold pages exist so far, and list tasks whose gold pages are all present."""
import json, os, sys, glob, ast
sys.path.insert(0, "lip/data")
import build_corpus as b
import bm25s
OUT = sys.argv[1]
os.makedirs(os.path.join(OUT, "gold"), exist_ok=True)
pages = []
for fn in glob.glob(os.path.join(b.CORPUS, "gold", "*.json")):
    r = json.load(open(fn))
    if r.get("missing") or not r.get("text"): continue
    tgt = os.path.join(OUT, "gold", os.path.basename(fn))
    if not os.path.exists(tgt): os.symlink(os.path.abspath(fn), tgt)
    pages.append(dict(title=r["title"], file="gold/" + os.path.basename(fn), kind="gold", n_chars=len(r["text"]), head=r["text"][:200], requested=r["requested"]))
seen=set(); uniq=[]
for p in pages:
    if p["title"] in seen: continue
    seen.add(p["title"]); uniq.append(p)
with open(os.path.join(OUT, "pages.jsonl"), "w") as f:
    for p in uniq: f.write(json.dumps(p) + "\n")
docs = [(p["title"] + " ") * 3 + json.load(open(os.path.join(OUT, p["file"])))["text"][:2000] for p in uniq]
idx = bm25s.BM25(); idx.index(bm25s.tokenize(docs, stopwords="en", show_progress=False), show_progress=False); idx.save(os.path.join(OUT, "index"))
have = {p["requested"] for p in pages}
ready = []
for l in open("lip/data/tasks.jsonl"):
    t = json.loads(l)
    if all(b.url_to_title(u) in have for u in t["gold_links"]): ready.append(t["id"])
print(f"partial index: {len(uniq)} pages; tasks fully covered: {len(ready)}: {ready[:12]}")
