"""The relay's three tools over the offline corpus: search, open, finish.

Corpus() loads lip/data/corpus/{pages.jsonl,index/} lazily; page texts are read from disk on
open (cached). Chunking is character-based: CHUNK_CHARS ~ 1500 tokens.
"""
import json, os, re, threading

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.abspath(os.path.join(HERE, "..", "data", "corpus"))
CHUNK_CHARS = 6000
SNIPPET_CHARS = 160
TOP_K = 5

TOOL_SPECS = [
    {"name": "search",
     "description": f"Keyword search over an offline snapshot of English Wikipedia. Returns the top {TOP_K} page titles with a short snippet each.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "keywords to search for"}}, "required": ["query"]}},
    {"name": "open",
     "description": "Open a page by its exact title (as returned by search). Returns one chunk of the page text; use page=2,3,... for later chunks.",
     "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "page": {"type": "integer", "description": "chunk number, default 1"}}, "required": ["title"]}},
    {"name": "finish",
     "description": "Submit the final answer to the question and stop. Give exactly one short answer (a name, number, date, word, or short list).",
     "parameters": {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}},
]

def _norm_title(t):
    return re.sub(r"\s+", " ", (t or "").strip().replace("_", " ")).lower()

class Corpus:
    _inst = None; _lock = threading.Lock()

    @classmethod
    def get(cls):
        with cls._lock:
            if cls._inst is None: cls._inst = cls()
            return cls._inst

    def __init__(self, root=CORPUS):
        import bm25s
        self.root = root
        self.pages = [json.loads(l) for l in open(os.path.join(root, "pages.jsonl"))]
        self.by_title = {_norm_title(p["title"]): i for i, p in enumerate(self.pages)}
        self.idx = bm25s.BM25.load(os.path.join(root, "index"))
        self._bm25s = bm25s
        self._text_cache = {}; self._clock = threading.Lock()

    def text(self, i):
        with self._clock:
            if i not in self._text_cache:
                self._text_cache[i] = json.load(open(os.path.join(self.root, self.pages[i]["file"])))["text"]
            return self._text_cache[i]

    def search(self, query, k=TOP_K):
        q = self._bm25s.tokenize([query or ""], stopwords="en", show_progress=False)
        res, scores = self.idx.retrieve(q, k=min(k, len(self.pages)), show_progress=False)
        out = []
        for j, s in zip(res[0], scores[0]):
            p = self.pages[int(j)]
            snip = self.snippet(int(j), query)
            out.append(dict(title=p["title"], snippet=snip, score=float(s)))
        return out

    def snippet(self, i, query):
        """Sentence-ish window around the first query-term hit, else the page head."""
        t = self.text(i)
        terms = [w for w in re.findall(r"\w+", (query or "").lower()) if len(w) > 2]
        low = t.lower(); best = None
        for w in terms:
            k = low.find(w)
            if k >= 0 and (best is None or k < best): best = k
        start = 0 if best is None else max(0, best - 60)
        s = t[start:start + SNIPPET_CHARS].replace("\n", " ")
        return ("…" if start else "") + s + "…"

    def open(self, title, page=1):
        i = self.by_title.get(_norm_title(title))
        if i is None:
            # cheap fallback: best BM25 hit on the title string, if it is an obvious match
            hits = self.search(title, k=3)
            cand = [h for h in hits if _norm_title(h["title"]) == _norm_title(title)]
            if not cand:
                return dict(error=f"No page titled {title!r}. Closest titles: " + "; ".join(h["title"] for h in hits))
            i = self.by_title[_norm_title(cand[0]["title"])]
        t = self.text(i)
        n = max(1, (len(t) + CHUNK_CHARS - 1) // CHUNK_CHARS)
        try: page = int(page or 1)
        except Exception: page = 1
        page = min(max(page, 1), n)
        chunk = t[(page - 1) * CHUNK_CHARS: page * CHUNK_CHARS]
        return dict(title=self.pages[i]["title"], page=page, n_pages=n, text=chunk)

def render(name, result):
    """Tool result -> the text the agent sees."""
    if name == "search":
        return "\n".join(f"{k+1}. {r['title']} — {r['snippet']}" for k, r in enumerate(result)) or "(no results)"
    if name == "open":
        if "error" in result: return result["error"]
        return f"[{result['title']} — chunk {result['page']} of {result['n_pages']}]\n{result['text']}"
    return str(result)
