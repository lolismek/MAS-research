"""Scoring for chainloss: exact outcome (secondary) + fact-level recall (primary).

Forked from multi-benchmark-eval:duet/harness/scoring.py, trimmed to the answer
types chainloss runs (freeform / list / qa) and extended with `list_recall`: the
all-or-nothing list matcher's per-item logic is refactored into `_item_hit` so
exact match and recall CANNOT drift apart — recall is the mean of the very same
per-item predicate the exact scorer conjoins.

Why recall is primary here: the thesis is about INFORMATION loss, so the graded
"how many gold facts survived to the final answer" carries the signal; duet P4
showed all-or-nothing FanOutQA sits near floor (28.8% vanilla), which would leave
no dynamic range for a degradation curve.
"""
import json
import re

# --- abstention -------------------------------------------------------------
_ABSTAIN = {"unknown", "unknowable", "i don't know", "idk", "n/a", "na", "none",
            "cannot determine", "can't determine", "insufficient evidence", ""}


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[,$%]", "", (s or "").strip().lower()))


def is_abstention(final):
    """The sanctioned abstain output. Kept narrow on purpose: a real answer that
    merely *contains* the word 'unknown' shouldn't be mistaken for an abstention,
    so we match the whole normalized answer, not a substring."""
    return _norm(final) in _ABSTAIN


# --- shared numeric/alias helpers -------------------------------------------
def _as_num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _num_eq(a, b):
    """Numeric equality when BOTH sides parse as numbers — so '$8.00'==8, '64.0'==64.
    (_norm already stripped $ , %.) Falls through to string compare otherwise."""
    x, y = _as_num(a), _as_num(b)
    return x is not None and y is not None and abs(x - y) <= 1e-9 * max(1.0, abs(y))


def _match_freeform(final, expected):
    nf, ne = _norm(final), _norm(expected)
    return nf == ne or _num_eq(nf, ne)


def _alias_hit(nf, na):
    """na (a normalized alias) hits nf (normalized final) on whole-answer equality OR
    a word-bounded mention. Word-bounded, NOT raw substring: short aliases like 'pol'
    would falsely match inside 'polish' — \\b stops that, while still crediting
    'he is a politician' for the alias 'politician'."""
    return bool(na) and (nf == na or re.search(r"\b" + re.escape(na) + r"\b", nf) is not None)


def _match_qa(final, expected):
    """`expected` is a JSON-encoded alias list (PopQA `possible_answers`). Correct if
    any alias hits the answer. EM/word-bounded, not loose substring, so a rambling
    wrong answer that merely contains an alias word isn't credited."""
    try:
        aliases = json.loads(expected)
    except (TypeError, ValueError):
        aliases = [expected]
    nf = _norm(final)
    return any(_alias_hit(nf, _norm(a)) for a in aliases)


# --- list answers (FanOutQA) -------------------------------------------------
def _initials(s):
    """Collapse spelled initials so 'j. j. abrams' == 'j.j. abrams' == 'jj abrams'."""
    return re.sub(r"\b([a-z])\.\s*", r"\1", s)


def _text_views(text):
    """The three views of a reply the per-item matcher checks against: the whole
    normalized text, its list-ish tokens (split on , ; newline ' and '), and its
    list segments (split on , ; newline only). Precomputed once per reply."""
    nf = _norm(text)
    nf_tokens = [_norm(t) for t in re.split(r"[,;\n]| and ", text or "")]
    segments = [_norm(t) for t in re.split(r"[,;\n]", text or "")]
    return nf, nf_tokens, segments


def _item_hit(views, gold_item):
    """Does ONE gold item appear in the reply? Word-bounded or numeric; with the
    three relaxations inherited from duet (validated there): initials-spacing is
    normalized; a compound item ('Anthony Russo and Joe Russo') hits when ALL its
    conjuncts hit individually; and a compound item also hits when all its content
    tokens land inside ONE list segment of the reply — so the factored surname
    'Anthony and Joe Russo' counts, but the same tokens scattered across different
    list items ('Joe Russo, Anthony Curtis') do not."""
    nf, nf_tokens, segments = views
    ng = _norm(str(gold_item))
    if not ng:
        return True                       # vacuous item: never fail on it
    if _alias_hit(nf, ng) or _alias_hit(_initials(nf), _initials(ng)):
        return True
    if any(_num_eq(t, ng) or t == ng for t in nf_tokens):
        return True
    parts = [p for p in re.split(r"\s+and\s+|\s*&\s*", ng) if p]
    if len(parts) > 1:
        if all(_alias_hit(nf, p) for p in parts):
            return True
        toks = [w for w in ng.split() if w not in ("and", "&")]
        if any(all(re.search(rf"\b{re.escape(w)}\b", seg) for w in toks)
               for seg in segments):
            return True
    return False


def _gold_list(expected):
    try:
        gold = json.loads(expected)
    except (TypeError, ValueError):
        gold = [expected]
    return gold if isinstance(gold, list) else [gold]


def _match_list(final, expected):
    """Correct iff EVERY gold item appears in the reply (order-insensitive; extra
    prose tolerated). One missing/wrong branch fails the whole answer."""
    views = _text_views(final)
    return all(_item_hit(views, g) for g in _gold_list(expected))


_MATCHERS = {"freeform": _match_freeform, "qa": _match_qa, "list": _match_list}


def match(final, expected, answer_type="freeform"):
    return _MATCHERS.get(answer_type, _match_freeform)(final, expected)


def gold_items(expected, answer_type="freeform"):
    """The gold facts a reply must carry, as a list (len 1 for scalar answers).
    The unit the recall and fact-survival metrics count over."""
    return _gold_list(expected) if answer_type == "list" else [expected]


def item_hit_in_text(text, gold_item):
    """One gold item vs an arbitrary text (final answer, hand-off note, transcript
    chunk) — the fact-survival probe. Same predicate as the exact scorer."""
    return _item_hit(_text_views(text), gold_item)


def list_recall(final, expected, answer_type="freeform"):
    """PRIMARY metric: fraction of gold items present in the reply. For scalar
    answer types this degenerates to 1.0/0.0 (= exact match). An abstention scores
    0.0 by construction (no gold item appears in 'UNKNOWN')."""
    if answer_type == "list":
        gold = _gold_list(expected)
        if not gold:
            return None
        views = _text_views(final)
        return sum(1 for g in gold if _item_hit(views, g)) / len(gold)
    return 1.0 if match(final, expected, answer_type) else 0.0


def classify_outcome(final, expected, answer_type="freeform", committed=True):
    """correct / abstained / no_answer / wrong_confident (secondary, honesty axis).

    `committed` is False when the run never emitted a parseable `FINAL ANSWER:`
    line. Such a non-answer is NOT a confident hallucination, so it gets its own
    bucket instead of inflating `wrong_confident`. Abstention is checked first
    (honest UNKNOWN); a truncated reply that still happens to contain the right
    answer is credited as correct."""
    if is_abstention(final):
        return "abstained"
    if match(final, expected, answer_type):
        return "correct"
    if not committed:
        return "no_answer"
    return "wrong_confident"
