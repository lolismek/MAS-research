"""Answer scoring: normalized exact match + strict LLM judge (gpt-5.4-mini via Perplexity).

score(question, gold, candidate) -> dict(correct: bool, em: bool, judge: 'CORRECT'|'INCORRECT'|None, reason)
Rule: correct = em or judge==CORRECT. em is a pure-string check so it never needs the API.
"""
import json, os, re, string, sys
sys.path.insert(0, os.path.dirname(__file__))
from llm import PplxResponses

JUDGE_MODEL = "openai/gpt-5.4-mini"
_judge = None

def normalize(s):
    s = (s or "").lower().strip()
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    s = s.translate(str.maketrans("", "", string.punctuation))
    s = re.sub(r"\s+", " ", s).strip()
    return s

def exact_match(gold, cand):
    g, c = normalize(gold), normalize(cand)
    return bool(g) and (g == c)

JUDGE_SYS = """You are a strict grader for a factual question-answering benchmark.
You are given a question, the gold answer, and a candidate answer. Decide whether the candidate
answer is correct, i.e. it states the SAME answer as the gold answer.

Rules:
- Names: the same person/place/entity counts even if written differently (e.g. with/without middle name).
- Numbers and dates must match the gold value. Trivial formatting differences (commas, units spelled out,
  "1,234" vs "1234", "Jan 5 1990" vs "5 January 1990") are fine. A different value is INCORRECT.
- If the gold answer is a list, the candidate must contain the same items (order irrelevant) and no wrong ones.
- Extra explanation in the candidate is fine as long as it commits to one final answer that matches.
- A candidate that hedges between several answers, or gives no answer, is INCORRECT.
- Do not use your own knowledge of the world: grade only candidate-vs-gold.

Reply with JSON only: {"verdict": "CORRECT" or "INCORRECT", "reason": "<one short sentence>"}"""

def llm_judge(question, gold, cand, tag="judge"):
    global _judge
    if _judge is None: _judge = PplxResponses(model=JUDGE_MODEL, effort="low", max_output_tokens=300)
    prompt = f"Question: {question}\n\nGold answer: {gold}\n\nCandidate answer: {cand}\n\nJSON verdict:"
    r = _judge.ask(prompt, system=JUDGE_SYS, tag=tag)
    m = re.search(r"\{.*\}", r["text"], re.S)
    try:
        j = json.loads(m.group(0)) if m else {}
    except Exception:
        j = {}
    v = str(j.get("verdict", "")).upper()
    return dict(judge=("CORRECT" if v == "CORRECT" else "INCORRECT" if v == "INCORRECT" else None),
                reason=j.get("reason", r["text"][:200]), cost=r["cost"])

def score(question, gold, cand, tag="judge", use_llm=True):
    em = exact_match(gold, cand)
    if em or not use_llm or not (cand or "").strip():
        return dict(correct=em, em=em, judge=None, reason="em" if em else "empty-or-no-llm")
    j = llm_judge(question, gold, cand, tag=tag)
    return dict(correct=(j["judge"] == "CORRECT"), em=False, judge=j["judge"], reason=j["reason"])
