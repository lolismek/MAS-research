"""Benchmark selection: LIP_BENCH=frames (default) | fanoutqa | bcp.

Everything benchmark-specific that the harness needs: corpus dir, how the corpus is described to agents and to the
oracle, the finish() length limits, and the task files. FRAMES values are the original hard-coded ones.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))
BENCH = os.environ.get("LIP_BENCH", "frames")

CFG = {
    "frames": dict(corpus=os.path.join(DATA, "corpus"),
                   search_desc="an offline snapshot of English Wikipedia",
                   oracle_desc="an offline Wikipedia snapshot",
                   finish_chars=200, finish_words=25,
                   tasks_all=os.path.join(DATA, "tasks.jsonl"),
                   tasks=os.path.join(DATA, "tasks_screened.jsonl"),
                   closed_book=os.path.join(DATA, "closed_book.jsonl")),
    # FanOutQA answers are lists / {entity: value} maps, so finish() must admit a longer answer
    "fanoutqa": dict(corpus=os.path.join(DATA, "fanoutqa", "corpus"),
                     search_desc="an offline snapshot of English Wikipedia",
                     oracle_desc="an offline Wikipedia snapshot",
                     finish_chars=700, finish_words=120,
                     tasks_all=os.path.join(DATA, "fanoutqa", "tasks.jsonl"),
                     tasks=os.path.join(DATA, "fanoutqa", "tasks_screened.jsonl"),
                     closed_book=os.path.join(DATA, "fanoutqa", "closed_book.jsonl")),
    "bcp": dict(corpus=os.path.join(DATA, "bcp", "corpus"),
                search_desc="an offline collection of web pages",
                oracle_desc="an offline collection of web pages",
                finish_chars=200, finish_words=25,
                tasks_all=os.path.join(DATA, "bcp", "tasks.jsonl"),
                tasks=os.path.join(DATA, "bcp", "tasks_screened.jsonl"),
                closed_book=os.path.join(DATA, "bcp", "closed_book.jsonl")),
}[BENCH]
