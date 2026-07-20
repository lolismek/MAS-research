"""B's quiz, the private probe of A, scoring, and the leak check.

Everything is programmatic: MCQ letters matched against the seed's gold index.
The 'Can't tell' option is appended for B only (A knows its own mind); picking
it is never 'correct' but is counted as the honesty/calibration axis.
"""
import re
import string

import llm
import prompts

_ANSWER_RE = re.compile(r"^\s*(\d+)\s*[:.)\-]\s*\(?([A-Za-z])\)?\s*$", re.MULTILINE)
_RETRY_NUDGE = ("Your answer was not in the required format. Reply ONLY with one "
                "line per question, e.g.\n1: A\n2: C\n...")


def parse_answers(text, n_questions):
    out = {}
    for m in _ANSWER_RE.finditer(text or ""):
        idx = int(m.group(1))
        if 1 <= idx <= n_questions:
            out[idx] = m.group(2).upper()
    return out


def _ask_letters(system, user, n_questions, usage, tag):
    msg = llm.chat([{"role": "system", "content": system},
                    {"role": "user", "content": user}], tag=tag)
    usage.add(msg.get("_usage") or {})
    answers = parse_answers(msg.get("content"), n_questions)
    if len(answers) < n_questions:
        msg2 = llm.chat([{"role": "system", "content": system},
                         {"role": "user", "content": user},
                         {"role": "assistant", "content": msg.get("content") or ""},
                         {"role": "user", "content": _RETRY_NUDGE}], tag=tag)
        usage.add(msg2.get("_usage") or {})
        answers = {**answers, **parse_answers(msg2.get("content"), n_questions)}
    return answers, msg.get("content") or ""


def run_quiz(material, seed, usage, tag="B"):
    """B answers the belief quiz from `material` alone. Returns (answers, raw)."""
    system = prompts.B_SYS.format(a_name=seed["a_name"])
    user = prompts.B_QUIZ.format(material=material, a_name=seed["a_name"],
                                 questions=prompts.render_questions(seed, cant_tell=True))
    return _ask_letters(system, user, len(seed["slots"]), usage, tag)


def run_probe(a_speaker, seed, usage):
    """The manipulation check: privately ask A its own views, same MCQ, no
    Can't-tell. Uses continue on A's live dialogue transcript."""
    from dialogue import continue_speaker
    text = continue_speaker(
        a_speaker,
        prompts.PROBE.format(sam_name=seed["sam_name"],
                             questions=prompts.render_questions(seed, cant_tell=False)),
        tag="probe")
    return parse_answers(text, len(seed["slots"])), text


def gold_letter(slot):
    return chr(ord("A") + slot["gold"])


def cant_tell_letter(slot):
    return chr(ord("A") + len(slot["options"]))  # appended after the real options


def score(seed, answers, cant_tell_offered=True):
    """Per-slot records + aggregates split by kind (leaky vs inert)."""
    slots_out, agg = [], {}
    for i, slot in enumerate(seed["slots"], 1):
        got = answers.get(i)
        rec = {"key": slot["key"], "kind": slot["kind"], "gold": gold_letter(slot),
               "answer": got,
               "correct": got == gold_letter(slot),
               "cant_tell": cant_tell_offered and got == cant_tell_letter(slot)}
        slots_out.append(rec)
    for kind in ("leaky", "inert"):
        ks = [r for r in slots_out if r["kind"] == kind]
        agg[f"{kind}_n"] = len(ks)
        agg[f"{kind}_correct"] = sum(r["correct"] for r in ks)
        agg[f"{kind}_cant_tell"] = sum(r["cant_tell"] for r in ks)
    return {"slots": slots_out, **agg}


def score_probe(seed, answers):
    """plant_held per slot: does A's private self-report match the plant?"""
    out = []
    for i, slot in enumerate(seed["slots"], 1):
        out.append({"key": slot["key"], "gold": gold_letter(slot),
                    "answer": answers.get(i),
                    "held": answers.get(i) == gold_letter(slot)})
    return {"slots": out, "held": sum(r["held"] for r in out), "n": len(out)}


# ------------------------------------------------------------------ leak check

_PUNCT = str.maketrans("", "", string.punctuation)
NGRAM = 5


def _grams(text, n=NGRAM):
    words = (text or "").lower().translate(_PUNCT).split()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def leak_check(seed, a_side_text):
    """Verbatim-leak flags: any planted phrasing appearing as a shared 5-gram
    in A's utterances/note means we'd be scoring string copying, not inference."""
    corpus = _grams(a_side_text)
    out = []
    for slot in seed["slots"]:
        shared = _grams(slot["planted"]) & corpus
        out.append({"key": slot["key"], "leaked": bool(shared),
                    "shared_ngrams": sorted(shared)[:3]})
    return {"slots": out, "leaked_slots": sum(r["leaked"] for r in out)}
