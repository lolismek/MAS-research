"""GAIA-style answer scorer.

Mirrors the spirit of the official GAIA scorer: numbers compared as floats
(commas/units stripped), strings normalized (lowercase, punctuation/articles
removed, whitespace collapsed), comma-lists compared element-wise. Used to score
BOTH the original Magentic-One `FINAL ANSWER:` and our new MAF runs against
`expected_answer.txt`.
"""
import re
import string


def _normalize_number(s: str):
    s = s.replace(",", "").replace("$", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


_ARTICLES = {"a", "an", "the"}


def _normalize_str(s: str) -> str:
    s = s.lower().strip()
    s = s.translate(str.maketrans("", "", string.punctuation))
    toks = [t for t in s.split() if t not in _ARTICLES]
    return " ".join(toks)


def _split_list(s: str):
    parts = [p for p in re.split(r"[,;]", s) if p.strip()]
    return parts if len(parts) > 1 else None


def grade(pred: str, gold: str) -> bool:
    """Return True iff `pred` matches `gold` under GAIA-style normalization."""
    if pred is None or gold is None:
        return False
    pred, gold = str(pred).strip(), str(gold).strip()
    if not pred:
        return False

    # numeric
    pn, gn = _normalize_number(pred), _normalize_number(gold)
    if pn is not None and gn is not None:
        return abs(pn - gn) < 1e-6 or (gn != 0 and abs(pn - gn) / abs(gn) < 1e-4)

    # list (element-wise, order-sensitive like GAIA)
    pl, gl = _split_list(pred), _split_list(gold)
    if gl is not None:
        if pl is None or len(pl) != len(gl):
            return False
        return all(grade(a, b) for a, b in zip(pl, gl))

    # string
    return _normalize_str(pred) == _normalize_str(gold)


FINAL_ANSWER_RE = re.compile(r"FINAL ANSWER:\s*(.+)")


def extract_final_answer(console_log_text: str):
    """Pull the last `FINAL ANSWER: ...` line from a Magentic-One console log."""
    matches = FINAL_ANSWER_RE.findall(console_log_text)
    return matches[-1].strip() if matches else None


if __name__ == "__main__":
    # quick self-checks
    assert grade("6", "6")
    assert grade("Rockhopper Penguin", "Rockhopper penguin")
    assert grade("1,234", "1234")
    assert not grade("7", "6")
    assert grade("a, b, c", "a,b,c")
    print("grade.py self-checks passed")
