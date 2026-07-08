"""Offline scoring tests — regressions caught live during smoke runs. NO LLM."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "harness"))
from scoring import classify_outcome, match  # noqa: E402

_FANOUT_GOLD = ('["James Cameron", "Anthony Russo and Joe Russo", "James Cameron", '
                '"James Cameron", "J. J. Abrams"]')


def test_list_every_item_required():
    assert match("James Cameron, Anthony Russo and Joe Russo, J. J. Abrams", _FANOUT_GOLD, "list")
    # a missing branch fails the whole answer — that is FanOutQA's point
    assert not match("James Cameron, Anthony Russo and Joe Russo", _FANOUT_GOLD, "list")
    print("ok  test_list_every_item_required")


def test_list_initials_spacing():
    """Live regression (fanout_002 pinned re-run): 'J.J. Abrams' failed against gold
    'J. J. Abrams' on initials spacing alone."""
    ans = "James Cameron, Anthony Russo, Joe Russo, James Cameron, James Cameron, J.J. Abrams"
    assert match(ans, _FANOUT_GOLD, "list")
    print("ok  test_list_initials_spacing")


def test_list_compound_gold_item():
    """A compound gold item ('X and Y') hits when all conjuncts hit individually —
    and still fails when one conjunct is absent."""
    assert match("Cameron x3, then Anthony Russo, Joe Russo, and J. J. Abrams; James Cameron",
                 _FANOUT_GOLD, "list")
    assert not match("James Cameron, Anthony Russo, James Cameron, James Cameron, J. J. Abrams",
                     _FANOUT_GOLD, "list")
    print("ok  test_list_compound_gold_item")


def test_list_wrong_answer_still_fails():
    """The pre-pin live answer (today's box office, Ne Zha 2 / no Abrams) must not match."""
    ans = "James Cameron, Anthony Russo, Joe Russo, James Cameron, James Cameron, Jiaozi"
    assert not match(ans, _FANOUT_GOLD, "list")
    assert classify_outcome(ans, _FANOUT_GOLD, "list") == "wrong_confident"
    print("ok  test_list_wrong_answer_still_fails")


def test_list_numeric_items():
    assert match("the answers are 1,234,567 and 42", '["1234567", "42"]', "list")
    assert not match("the answers are 1,234,568 and 42", '["1234567", "42"]', "list")
    print("ok  test_list_numeric_items")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nALL {len(fns)} SCORING OFFLINE TESTS PASSED")
