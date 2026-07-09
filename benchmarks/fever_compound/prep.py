"""FEVER-compound -> tasks.jsonl — the duet BRIDGE benchmark (PLAN "Hub benchmarks").

FEVER claims filtered to those asserting >=2 INDEPENDENTLY CHECKABLE facts, so the
decomposition is native, not manufactured: a compound claim verifies naturally in
shifts (relay) or in parallel branches (hub) — the same tasks run on BOTH topologies,
the cleanest geometry-vs-geometry comparison in the study.

Source: `copenlu/fever_gold_evidence` test split (same as benchmarks/fever). Filter =
textual compoundness: >=2 coordinated predicates ("X did A and did B", "X, who ...,
also ...", apposition + predicate). Multi-page evidence was tried as a second signal
and REJECTED: in this flattened export, rows whose evidence spans >=2 pages are
mostly ALTERNATIVE sufficient evidence sets for one atomic fact ("Hermit crabs are
animals" passes via 2 pages) — it selects redundancy, not compoundness. It is kept in
meta as bookkeeping only.
An optional LLM screen runs over the heuristic survivors (FEVER_COMPOUND_LLM=1, via
the shared proxy): "does this claim assert two or more separately checkable facts?" —
PLAN flags filter quality as a known risk; the screen is the second pass.

Class-balanced (~PER_CLASS each, round-robin) so a small --limit smoke still covers
all three labels. NEI is a GOLD label (label-level honesty ground truth), NOT an
abstention — scoring maps a model's "unknown" onto NEI (see benchmarks/fever/prep.py).

Unlike closed-book benchmarks/fever, duet runs the bridge OPEN-BOOK (tool_profile
"web"): the claim is decomposable AND checkable, which is what makes it exercise
hand-offs / fan-out rather than parametric knowledge.

Run:
  conda run -n autogen_gc python benchmarks/fever_compound/prep.py
  FEVER_COMPOUND_PER_CLASS=25 FEVER_COMPOUND_LLM=1 conda run -n autogen_gc python benchmarks/fever_compound/prep.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import hf_token, write_tasks  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PER_CLASS = int(os.environ.get("FEVER_COMPOUND_PER_CLASS", "25"))   # ~75 total, PLAN 60-80
LABELS = ["SUPPORTS", "REFUTES", "NOT ENOUGH INFO"]
LLM_SCREEN = os.environ.get("FEVER_COMPOUND_LLM", "") == "1"
PROXY = os.environ.get("PROXY_URL", "http://127.0.0.1:8744/v1")

PROMPT = ("Claim: {claim}\n\nDecide whether the claim is SUPPORTED or REFUTED by "
          "publicly available evidence, or whether there is NOT ENOUGH INFO to decide. "
          "Every part of the claim must hold for it to be supported. Answer with "
          "exactly one of: SUPPORTS, REFUTES, NOT ENOUGH INFO.")

# --- signal 2: textual compoundness -------------------------------------------
# Two-or-more coordinated predicates / an apposition plus a predicate. Deliberately
# conservative: plain entity conjunction inside one fact ("A and B starred in X")
# does NOT pass — the coordination must join VERB phrases or clause boundaries.
_COORD_VP = re.compile(
    r"\b(and|but)\s+(?:is|was|were|are|has|had|have|also|later|then|won|wrote|directed|"
    r"played|starred|produced|released|founded|created|became|served|received|holds?)\b",
    re.I)
_REL_CLAUSE = re.compile(r",\s*(?:who|which|whose|where)\b.+?,", re.I)
_APPOSITION = re.compile(r"^[A-Z][^,]+,\s+(?:an?|the)\s+[^,]+,\s+\w+")


def textually_compound(claim):
    c = claim.strip()
    return bool(_COORD_VP.search(c) or _REL_CLAUSE.search(c) or _APPOSITION.search(c))


# --- NEI label-noise screen (hand-review, 2026-07-07) ---------------------------
# FEVER's NOT-ENOUGH-INFO is relative to the 2017 wiki snapshot. Run OPEN-BOOK, an
# NEI gold is only trustworthy when the claim has a genuinely unverifiable conjunct
# ("has a fan base", "is highly usable") — those measure honest abstention. NEI
# claims where EVERY part is objectively decidable today (or one part is verifiably
# false, which decides the whole claim under "every part must hold") are label
# noise and are excluded by original_id below. Reviewed by hand; extend this list
# when regenerating with a larger PER_CLASS.
_NEI_NOISY_IDS = {
    161127,  # "Jarhead ... produced by Sam Mendes" — Mendes directed it; decidable
    158310,  # "Kenny Chesney ... born in Kentucky" — born in Knoxville, TN; decidable REFUTES
    171489,  # "Jiang Wen is from China and is a professional director" — decidable SUPPORTS
    34750,   # "Night of the Living Dead ... created the image of the modern zombie" — documented
    23956,   # "electric chair ... South Carolina, and redwood" — ill-formed mutation, models REFUTE
    109365,  # "MiLB ... International League, Pacific Coast League, Mexican League" — all checkable
    54055,   # "electric chair is NOT optional in AL/FL/SC/VA as of 2014" — it was; decidable REFUTES
    4868,    # "Shannon Lee born in 1969 and is a Baby Boomer" — 1969 > 1964; decidable REFUTES
    18452,   # "Yugoslavia consisted of the coterminous Balkan peninsula" — decidably false conjunct
    168077,  # "Jean-Jacques Dessalines was a pacifist" — decidably false
    188653,  # "Foot Locker's full business name ... stock market" — listing name checkable
    191882,  # "Padua ... located 30 miles from Rome" — ~300 miles; decidable REFUTES
    134439,  # "Harrison divorced Pattie Boyd, who acted in Help!, in 1977" — all conjuncts checkable
    108308,  # "Louie (season 1) written/directed by Louis C.K., based on his life" — documented
    109606,  # "Caesar was directed and produced by Cary Grant" — Grant never directed; decidable
    # near-duplicate NEI families (same unverifiable conjunct, keep <=2 per family):
    101505,  # 4th "John S. McCain Jr. ... has a fan base" variant
    121571,  # 3rd "John S. McCain Jr. ... has a fan base" variant
    18088,   # 2nd "Python ... is very usable" variant
}


def nei_noisy(row):
    return row.get("label") == "NOT ENOUGH INFO" and row.get("original_id") in _NEI_NOISY_IDS


def multi_page(row):
    pages = {e[0] for e in row.get("evidence") or [] if e and e[0]}
    return len(pages) >= 2


def is_compound(row):
    return textually_compound(row["claim"])


# --- optional LLM screen over heuristic survivors ------------------------------
_SCREEN_PROMPT = (
    "Claim: {claim}\n\n"
    "Does this claim assert TWO OR MORE separately checkable factual statements "
    "(each of which could be verified on its own)? Answer with exactly one word: "
    "YES or NO.")


def llm_pass(claim):
    from openai import OpenAI
    base, v1 = PROXY.rsplit("/", 1)
    client = OpenAI(base_url=f"{base}/m/fever_compound_prep/{v1}", api_key="dummy")
    r = client.chat.completions.create(
        model="gpt-4o", temperature=0.0, max_tokens=2048,
        messages=[{"role": "user", "content": _SCREEN_PROMPT.format(claim=claim)}])
    return "yes" in (r.choices[0].message.content or "").strip().lower()[:6]


def build():
    from huggingface_hub import hf_hub_download
    path = hf_hub_download("copenlu/fever_gold_evidence", "test.jsonl",
                           repo_type="dataset", token=hf_token())
    buckets = {l: [] for l in LABELS}
    seen_claims = set()
    scanned = kept = 0
    for line in open(path):
        r = json.loads(line)
        lab = r.get("label")
        scanned += 1
        if lab not in buckets or len(buckets[lab]) >= PER_CLASS * (3 if LLM_SCREEN else 1):
            continue
        claim = r["claim"].strip()
        if claim.lower() in seen_claims or not is_compound(r) or nei_noisy(r):
            continue
        seen_claims.add(claim.lower())
        buckets[lab].append(r)
        kept += 1
        if all(len(v) >= PER_CLASS * (3 if LLM_SCREEN else 1) for v in buckets.values()):
            break
    print(f"heuristic pass: kept {kept}/{scanned} scanned "
          f"({ {l: len(v) for l, v in buckets.items()} })")

    if LLM_SCREEN:                       # second pass: keep only LLM-confirmed compounds
        for lab in LABELS:
            confirmed = []
            for r in buckets[lab]:
                if len(confirmed) >= PER_CLASS:
                    break
                if llm_pass(r["claim"]):
                    confirmed.append(r)
            print(f"LLM screen [{lab}]: {len(confirmed)}/{len(buckets[lab])} confirmed")
            buckets[lab] = confirmed

    tasks, i = [], 0
    for k in range(PER_CLASS):                       # round-robin across labels
        for lab in LABELS:
            if k >= len(buckets[lab]):
                continue
            r = buckets[lab][k]
            pages = sorted({e[0] for e in r.get("evidence") or [] if e and e[0]})
            tasks.append(dict(
                id=f"feverc_{i:03d}", bench="fever_compound",
                question=PROMPT.format(claim=r["claim"].strip()),
                expected_answer=lab, answer_type="label", tool_profile="web",
                meta=dict(label=lab, verifiable=r.get("verifiable"),
                          original_id=r.get("original_id"), evidence_pages=pages,
                          multi_page=multi_page(r),
                          textually_compound=textually_compound(r["claim"]),
                          llm_screened=LLM_SCREEN)))
            i += 1
    write_tasks(os.path.join(HERE, "tasks.jsonl"), tasks)


if __name__ == "__main__":
    build()
