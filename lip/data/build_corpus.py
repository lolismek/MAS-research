"""Build the offline FRAMES corpus.

Stages (each resumable; run in order):
  gold       fetch every gold page of all 824 questions at its last revision before
             2024-08-01 (parse HTML -> text with tables kept row-wise; outlinks recorded)
  neighbors  fetch a fixed-seed sample of one-hop outlink neighbors (latest wikitext ->
             text) as distractors
  index      chunk pages and build the BM25 index used by the relay's search/open tools

Layout: lip/data/corpus/gold/<slug>.json, lip/data/corpus/neighbors/<slug>.json,
        lip/data/corpus/index/ (bm25s), lip/data/corpus/pages.jsonl (title -> file, kind)
"""
import ast, hashlib, json, os, random, re, sys, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote
import requests
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
API = "https://en.wikipedia.org/w/api.php"
UA = "lip-relay-research/0.1 (alex.jerpelea@gmail.com) python-requests"
PIN = "2024-08-01T00:00:00Z"
N_NEIGHBORS = int(os.environ.get("N_NEIGHBORS", "40000"))
WORKERS = int(os.environ.get("WORKERS", "4"))

_tls = threading.local()
def sess():
    if not hasattr(_tls, "s"):
        _tls.s = requests.Session(); _tls.s.headers["User-Agent"] = UA
    return _tls.s

def get(params, tries=6):
    params = dict(params, format="json", formatversion=2, maxlag=5)
    for k in range(tries):
        try:
            r = sess().get(API, params=params, timeout=60)
            if r.status_code == 200:
                j = r.json()
                if "error" in j and j["error"].get("code") == "maxlag":
                    time.sleep(2 + k); continue
                return j
            if r.status_code == 429:
                time.sleep(5 + 5 * k); continue
            time.sleep(1 + k)
        except Exception:
            time.sleep(1 + k)
    raise RuntimeError(f"wiki api failed: {params}")

def slug(title):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", title)[:80] + "_" + hashlib.md5(title.encode()).hexdigest()[:8]

def url_to_title(u):
    t = unquote(u.split("/wiki/", 1)[1]) if "/wiki/" in u else u
    return t.split("#")[0].replace("_", " ").strip()

_ANNOT = re.compile(r"\s*\((NOT REQUIRED|OPTIONAL)[^)]*\)\s*", re.I)

def parse_links(links):
    """FRAMES wiki_links entries -> list of page titles. Handles strings that pack several URLs
    ("A, https://.../B, https://.../C"), index.php?title=X URLs, and annotations. Unresolvable entries
    (Special:Search, w.wiki short links) are dropped."""
    out = []
    for raw in links:
        for part in re.split(r",\s*(?=https?://)", raw.strip()):
            part = _ANNOT.sub("", part).strip().rstrip(",").strip()
            if not part: continue
            if "Special:Search" in part or "w.wiki/" in part: continue
            m = re.search(r"index\.php\?(?:.*&)?title=([^&]+)", part)
            if m: part = unquote(m.group(1))
            t = url_to_title(part)
            if t and t not in out: out.append(t)
    return out

# ---------------------------------------------------------------- HTML -> text
DROP_SEL = ["style", "script", "sup.reference", ".mw-editsection", ".navbox", ".vertical-navbox",
            ".sidebar", ".reflist", ".mw-references-wrap", "#References", ".hatnote", ".ambox",
            ".metadata", ".noprint", "table.sistersitebox", ".portal", ".catlinks", ".shortdescription"]
STOP_HEADINGS = {"references", "external links", "further reading", "notes", "see also", "sources", "bibliography"}

def html_to_text(html):
    soup = BeautifulSoup(html, "lxml")
    for sel in DROP_SEL:
        for el in soup.select(sel): el.decompose()
    root = soup.select_one(".mw-parser-output") or soup
    out = []
    for el in root.children:
        name = getattr(el, "name", None)
        if name is None: continue
        if name in ("h2", "h3", "h4"):
            h = el.get_text(" ", strip=True)
            if h.lower() in STOP_HEADINGS: break
            out.append("\n== " + h + " ==")
        elif name == "table":
            rows = []
            for tr in el.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
                cells = [c for c in cells if c]
                if cells: rows.append(" | ".join(cells))
            if rows: out.append("[table]\n" + "\n".join(rows) + "\n[/table]")
        elif name in ("p", "ul", "ol", "dl", "blockquote", "div"):
            # divs: infobox-ish wrappers, thumbs; keep text but also inner tables
            for t in el.find_all("table"):
                rows = []
                for tr in t.find_all("tr"):
                    cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
                    cells = [c for c in cells if c]
                    if cells: rows.append(" | ".join(cells))
                t.replace_with("[table]\n" + "\n".join(rows) + "\n[/table]" if rows else "")
            txt = el.get_text(" ", strip=True) if name == "p" else el.get_text("\n", strip=True)
            if txt: out.append(txt)
    text = "\n".join(out)
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def wikitext_to_text(wt):
    import mwparserfromhell
    code = mwparserfromhell.parse(wt)
    txt = code.strip_code(normalize=True, collapse=True)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()

# ---------------------------------------------------------------- stage: gold
def fetch_gold(title):
    j = get(dict(action="query", titles=title, redirects=1, prop="revisions", rvprop="ids|timestamp",
                 rvstart=PIN, rvdir="older", rvlimit=1))
    pg = j["query"]["pages"][0]
    if pg.get("missing") or "revisions" not in pg:
        return dict(requested=title, missing=True)
    rev = pg["revisions"][0]
    j = get(dict(action="parse", oldid=rev["revid"], prop="text|links", disabletoc=1, disableeditsection=1))
    pinned = True
    if "parse" not in j:            # e.g. revision-deleted text: fall back to the current revision, flagged
        j = get(dict(action="parse", page=pg["title"], prop="text|links|revid", disabletoc=1, disableeditsection=1))
        pinned = False
        if "parse" not in j: return dict(requested=title, missing=True, error=str(j.get("error"))[:200])
    p = j["parse"]
    links = [l["title"] for l in p.get("links", []) if l.get("ns") == 0 and l.get("exists", True)]
    return dict(requested=title, title=pg["title"], pageid=pg.get("pageid"), revid=rev["revid"] if pinned else p.get("revid"),
                timestamp=rev["timestamp"] if pinned else None, pinned=pinned, text=html_to_text(p["text"]), links=links, kind="gold")

def stage_gold():
    import pandas as pd
    df = pd.read_csv(os.path.join(HERE, "frames_raw.csv"))
    titles = sorted({t for ls in df.wiki_links.map(ast.literal_eval) for t in parse_links(ls)})
    os.makedirs(os.path.join(CORPUS, "gold"), exist_ok=True)
    todo = [t for t in titles if not os.path.exists(os.path.join(CORPUS, "gold", slug(t) + ".json"))]
    print(f"gold: {len(titles)} unique titles, {len(todo)} to fetch", flush=True)
    done = 0; missing = 0
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(fetch_gold, t): t for t in todo}
        for f in as_completed(futs):
            t = futs[f]
            try:
                rec = f.result()
            except Exception as e:
                print("ERR", t, e, flush=True); continue
            if rec.get("missing"): missing += 1
            json.dump(rec, open(os.path.join(CORPUS, "gold", slug(t) + ".json"), "w"))
            done += 1
            if done % 100 == 0: print(f"  {done}/{len(todo)} missing={missing}", flush=True)
    print(f"gold done: {done} fetched, {missing} missing", flush=True)

# ---------------------------------------------------------------- stage: neighbors
def fetch_batch_latest(titles):
    j = get(dict(action="query", titles="|".join(titles), redirects=1, prop="revisions",
                 rvprop="ids|content", rvslots="main"))
    out = []
    for pg in j["query"]["pages"]:
        if pg.get("missing") or "revisions" not in pg: continue
        wt = pg["revisions"][0]["slots"]["main"]["content"]
        if wt.lower().startswith("#redirect"): continue
        out.append(dict(title=pg["title"], pageid=pg.get("pageid"), revid=pg["revisions"][0]["revid"],
                        text=wikitext_to_text(wt), kind="neighbor"))
    return out

def stage_neighbors():
    gold_dir = os.path.join(CORPUS, "gold")
    gold_titles, links = set(), set()
    for fn in os.listdir(gold_dir):
        rec = json.load(open(os.path.join(gold_dir, fn)))
        if rec.get("missing"): continue
        gold_titles.add(rec["title"]); links.update(rec["links"])
    cand = sorted(links - gold_titles)
    random.Random(0).shuffle(cand)
    cand = cand[:N_NEIGHBORS]
    nd = os.path.join(CORPUS, "neighbors"); os.makedirs(nd, exist_ok=True)
    have = {fn[:-5] for fn in os.listdir(nd)}
    todo = [t for t in cand if slug(t) not in have]
    print(f"neighbors: {len(links)} outlinks, {len(cand)} sampled, {len(todo)} to fetch", flush=True)
    batches = [todo[i:i + 50] for i in range(0, len(todo), 50)]
    n = 0
    with ThreadPoolExecutor(WORKERS) as ex:
        for recs in ex.map(fetch_batch_latest, batches):
            for rec in recs:
                json.dump(rec, open(os.path.join(nd, slug(rec["title"]) + ".json"), "w")); n += 1
            if n and n % 2000 < 50: print(f"  {n} saved", flush=True)
    print(f"neighbors done: {n} saved", flush=True)

# ---------------------------------------------------------------- stage: index
CHUNK_CHARS = 6000

def stage_index():
    import bm25s
    pages = []
    for kind in ("gold", "neighbors"):
        d = os.path.join(CORPUS, kind)
        for fn in sorted(os.listdir(d)):
            rec = json.load(open(os.path.join(d, fn)))
            if rec.get("missing") or not rec.get("text"): continue
            pages.append(dict(title=rec["title"], file=f"{kind}/{fn}", kind=rec["kind"],
                              n_chars=len(rec["text"]), head=rec["text"][:200]))
    # dedupe by title (a neighbor may resolve to a gold title via redirect) — gold wins
    seen, uniq = set(), []
    for p in pages:
        if p["title"] in seen: continue
        seen.add(p["title"]); uniq.append(p)
    with open(os.path.join(CORPUS, "pages.jsonl"), "w") as f:
        for p in uniq: f.write(json.dumps(p) + "\n")
    # index: title (weighted by repetition) + first 2000 chars
    docs = [(p["title"] + " ") * 3 + p["head"] + " " + json.load(open(os.path.join(CORPUS, p["file"])))["text"][:2000]
            for p in uniq]
    tok = bm25s.tokenize(docs, stopwords="en")
    idx = bm25s.BM25(); idx.index(tok)
    idx.save(os.path.join(CORPUS, "index"))
    print(f"index: {len(uniq)} pages ({sum(p['kind']=='gold' for p in uniq)} gold)", flush=True)

if __name__ == "__main__":
    {"gold": stage_gold, "neighbors": stage_neighbors, "index": stage_index}[sys.argv[1]]()
