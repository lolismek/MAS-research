"""L-PROBE v2 training data: a large DIVERSE pool of short snippets where the
author either plainly holds a STRONG belief about what is happening (label 1)
or is unsettled/uncertain (label 0).

Per the 2026-07-20 user directive (supersedes PLAN_V2's matched-pair scenario
design): no matched-pair construction — diversity does the controlling.
Diversity axes:
  - domain (debugging, ops incidents, narrative, analysis, QA/research,
    dialogue, code-reading, navigation, diagnosis, investigation)
  - style / first vs third person
  - CRITICAL: lexical marking. Half of each label is generated WITHOUT the
    obvious lexical markers: confident text with no "clearly/definitely/I'm
    sure" (the author just states and acts on the conclusion), and uncertain
    text with no hedge words (the evidence simply does not settle the matter,
    the author keeps gathering). Otherwise the probe learns hedge-word
    detection instead of internal conviction.
  - convinced-but-wrong text is included as label 1 (conviction, not truth).

Generation: Qwen3-8B via the vLLM endpoint (default the piranha :8804 tunnel),
temperature 0.9, JSON-array batches, threaded. Output:
latent/probe/synth_data.jsonl  {text, label, domain, marked, person}

Run on piranha:
  /tmp/aij2115/pyenv/bin/python -m latent.probe.gen_data --n-batches 6
"""
import argparse
import json
import os
import random
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "synth_data.jsonl")
VLLM = os.environ.get("SYNCHANDOFF_VLLM_BASE", "http://localhost:8804/v1")
MODEL = os.environ.get("SYNCHANDOFF_VLLM_MODEL", "Qwen/Qwen3-8B")

DOMAINS = {
    "debugging": "a software engineer investigating a failing test or bug in a codebase",
    "ops": "an on-call engineer working through a production incident from logs and dashboards",
    "narrative": "a character in a short story working out what is going on around them",
    "analysis": "a data analyst interpreting a table, chart, or experiment result",
    "qa": "a researcher answering a factual question from several source documents",
    "dialogue": "two colleagues talking through a problem (write it as a short dialogue)",
    "code_reading": "a developer reading unfamiliar code to work out what it does",
    "navigation": "someone finding their way through an unfamiliar building or city",
    "diagnosis": "a mechanic or clinician working out the cause of a fault or symptom",
    "investigation": "an investigator piecing together what happened from interviews and records",
}

STRONG_MARKED = (
    "The author has just become CONVINCED of what is happening — the evidence "
    "clicked and they now hold one settled conclusion. They may use natural "
    "confidence language.")
STRONG_UNMARKED = (
    "The author has just become CONVINCED of what is happening and holds one "
    "settled conclusion — but write it WITHOUT any explicit certainty words "
    "(no 'clearly', 'definitely', 'obviously', 'I'm sure', 'must be'). The "
    "conviction shows only through flat statement of the conclusion and "
    "immediately acting on it (e.g. going straight to the fix / the answer / "
    "the destination).")
STRONG_WRONG = (
    "The author has just become fully CONVINCED of a conclusion that is "
    "actually WRONG (the reader can tell from a subtle detail in the snippet "
    "that the evidence points elsewhere, but the author does not notice). "
    "The author's conviction must be total — no doubt expressed. Mix marked "
    "and unmarked confidence styles.")
UNSETTLED_MARKED = (
    "The author is genuinely UNCERTAIN about what is happening — several "
    "possibilities remain open, or the evidence is contradictory. They may "
    "use natural hedging language.")
UNSETTLED_UNMARKED = (
    "The situation is genuinely UNSETTLED — the evidence so far does not "
    "determine what is happening — but write it WITHOUT any hedge words (no "
    "'maybe', 'perhaps', 'might', 'not sure', 'unclear'). The uncertainty "
    "shows only structurally: the author lists observations that do not "
    "settle the matter, keeps gathering more, tries another angle, or notes "
    "two facts that pull in different directions, without committing to a "
    "conclusion.")

CELLS = [  # (cell_name, label, instruction)
    ("strong_marked", 1, STRONG_MARKED),
    ("strong_unmarked", 1, STRONG_UNMARKED),
    ("strong_wrong", 1, STRONG_WRONG),
    ("unsettled_marked", 0, UNSETTLED_MARKED),
    ("unsettled_unmarked", 0, UNSETTLED_UNMARKED),
]

PROMPT = """Write {n} short snippets (60-120 words each), each written from the
point of view of {domain_desc}. Use {person} person. The snippets must be
unrelated to each other (different concrete situations, names, systems,
places), concrete and specific, and each must END at the moment where the
author's current state of belief holds — no epilogue, no resolution after it.

{instruction}

Return ONLY a JSON array of {n} strings, no other text."""

_lock = threading.Lock()


def gen_batch(domain, cell, label, instruction, person, seed, n=8,
              temperature=0.9):
    body = {"model": MODEL, "temperature": temperature, "top_p": 0.95,
            "max_tokens": 4000, "seed": seed,
            "messages": [{"role": "user", "content": PROMPT.format(
                n=n, domain_desc=DOMAINS[domain], person=person,
                instruction=instruction)}]}
    r = requests.post(f"{VLLM}/chat/completions", json=body, timeout=600)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"] or ""
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return []
    out = []
    for s in arr:
        if isinstance(s, str) and 120 <= len(s) <= 1200:
            out.append({"text": s.strip(), "label": label, "domain": domain,
                        "cell": cell, "person": person})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-batches", type=int, default=6,
                    help="batches of 8 per (domain, cell)")
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    jobs = []
    seed = 1000
    for domain in DOMAINS:
        for cell, label, instr in CELLS:
            for b in range(args.n_batches):
                person = "first" if (b % 2 == 0) else "third"
                jobs.append((domain, cell, label, instr, person, seed))
                seed += 1
    random.Random(0).shuffle(jobs)
    print(f"{len(jobs)} generation batches (target ~{len(jobs)*8} snippets)")

    rows, seen = [], set()
    done = [0]

    def run(j):
        domain, cell, label, instr, person, sd = j
        try:
            batch = gen_batch(domain, cell, label, instr, person, sd)
        except Exception as e:
            print(f"  batch error {domain}/{cell}: {e}", flush=True)
            batch = []
        with _lock:
            for r in batch:
                key = re.sub(r"\W", "", r["text"].lower())[:80]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(r)
            done[0] += 1
            if done[0] % 25 == 0:
                print(f"  {done[0]}/{len(jobs)} batches, {len(rows)} snippets",
                      flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(run, jobs))

    with open(OUT, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    from collections import Counter
    print(f"wrote {len(rows)} snippets to {OUT}")
    print("by cell:", dict(Counter(r['cell'] for r in rows)))
    print("by domain:", dict(Counter(r['domain'] for r in rows)))


if __name__ == "__main__":
    main()
