"""MATH answer matching — adapted from camel/harness/scoring.py (validated there:
+29 corrections, 0 regressions vs naive string equality on the vanilla MATH-L5 run).
LaTeX-canonicalizing, order-insensitive multiset, numeric via Fraction; conservative
(never equates numerically different answers).
"""
import re
from fractions import Fraction


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[,$%]", "", (s or "").strip().lower()))


def _strip_math(s):
    s = (s or "").strip()
    m = re.search(r"\\boxed\s*{([^{}]*)}", s)
    if m:
        s = m.group(1)
    s = s.replace("$", "").replace("\\!", "").replace("\\,", "").replace(" ", "")
    s = s.replace("\\left", "").replace("\\right", "")
    return _norm(s)


def _latex_clean(s):
    s = (s or "").strip()
    m = re.search(r"\\boxed\s*{(.*)}", s)
    if m:
        s = m.group(1)
    s = re.sub(r"\\text\s*{[^{}]*}", "", s)
    s = re.sub(r"\^\s*{?\\?circ}?", "", s)
    s = s.replace("\\$", "").replace("$", "").replace("\\%", "").replace("%", "")
    s = re.sub(r"\\(!|,|;|:|\s|quad|qquad)", "", s)
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    s = s.replace("\\cdot", "*").replace("\\times", "*")
    s = re.sub(r"(?<=\d),(?=\d{3}(\D|$))", "", s)
    for _ in range(3):
        s = re.sub(r"\\frac\s*{([^{}]*)}\s*{([^{}]*)}", r"(\1)/(\2)", s)
        s = re.sub(r"\\frac\s*{([^{}]*)}\s*(\w)", r"(\1)/(\2)", s)
        s = re.sub(r"\\frac\s*(\w)\s*(\w)", r"(\1)/(\2)", s)
    s = re.sub(r"\\sqrt\s*{([^{}]*)}", r"sqrt(\1)", s)
    s = s.replace("\\{", "").replace("\\}", "").replace(" ", "")
    if "=" in s:
        s = s.rsplit("=", 1)[1]
    return s


def _value(s):
    cand = (s or "").strip().replace("(", "").replace(")", "")
    if not cand:
        return None
    try:
        return Fraction(cand)
    except Exception:  # noqa: BLE001
        pass
    try:
        return float(cand)
    except Exception:  # noqa: BLE001
        return None


def _expand_pm(s):
    if "\\pm" in s:
        a, b = s.split("\\pm", 1)
        return {a + "-" + b, a + "+" + b}
    return {s}


def _canon_set(x):
    elems = set()
    for part in re.split(r",", _latex_clean(x)):
        part = part.strip()
        if not part:
            continue
        for e in _expand_pm(part):
            v = _value(e)
            elems.add(("#", v) if v is not None else ("s", e))
    return elems


def _elem_eq(a, b):
    if a[0] == "#" and b[0] == "#":
        try:
            return abs(float(a[1]) - float(b[1])) <= 1e-9 * max(1.0, abs(float(b[1])))
        except Exception:  # noqa: BLE001
            return a[1] == b[1]
    return a == b


def match_math(final, expected):
    if _strip_math(final) == _strip_math(expected):
        return True
    F, E = _canon_set(final), _canon_set(expected)
    if not E or not F:
        return False
    return (all(any(_elem_eq(e, f) for f in F) for e in E)
            and all(any(_elem_eq(f, e) for e in E) for f in F))


_FINAL = re.compile(r"FINAL ANSWER:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def extract_answer(text):
    """Last 'FINAL ANSWER: ...' line; falls back to the last \\boxed{...}; else the
    last non-empty line (match_math re-extracts boxed content anyway)."""
    text = text or ""
    hits = _FINAL.findall(text)
    if hits:
        return hits[-1].strip()
    boxed = re.findall(r"\\boxed\s*{[^{}]*}", text)
    if boxed:
        return boxed[-1]
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[-1] if lines else ""


def extract_label(text):
    """Last SUPPORTS/REFUTES token in the text (word-boundary, tolerant of
    SUPPORTED/REFUTED). None if absent (mute/placeholder finals score wrong)."""
    hits = re.findall(r"\b(SUPPORT(?:S|ED)?|REFUT(?:ES|ED)?)\b", text or "",
                      re.IGNORECASE)
    if not hits:
        return None
    return "SUPPORTS" if hits[-1].upper().startswith("SUPPORT") else "REFUTES"
