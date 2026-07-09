"""Offline mechanics test for the DIALOGUE topology — NO LLM, NO network.

Asserts: persistent per-agent contexts (memory survives turns; only messages cross),
the propose -> ratify termination, the single contest, the turn-cap forced finalize,
and the unusable-message marker.

Run:  conda run -n autogen_gc python duet/tests/test_dialogue_offline.py
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "harness"))

import prompts
from agent import Budget
from dialogue import run_dialogue
from arms import get_addon
from _fakes import FakeClient, tool_turn, text_turn

PY = ["run_python"]


def budget():
    return Budget(10.0, 0.36, 0.89)


def test_propose_and_ratify():
    """A works (message), B works then proposes, A ratifies -> done with B's answer."""
    script = [
        tool_turn(("run_python", {"code": "print('a1')"})),      # A turn 1: one tool call
        text_turn("I checked part one; open: part two."),        # A's message (clean stop)
        tool_turn(("run_python", {"code": "print('b1')"})),      # B turn 2
        text_turn("Part two checks out. FINAL ANSWER: 42"),      # B proposes
        text_turn("DECISION: agree"),                            # A ratifies (turn 3)
    ]
    c = FakeClient(script)
    r = run_dialogue("solve it", PY, c, "m", get_addon("vanilla"), t_max=8,
                     turn_budget=3, usd_budget=budget())
    assert r.ratified is True and r.proposals == 1 and r.contests == 0
    assert "FINAL ANSWER: 42" in r.final, r.final
    assert r.turns_used == 3
    # persistence: A's final state still holds its OWN turn-1 tool call...
    a_state = r.states["peer_A"]
    assert any("print('a1')" in ((tc.get("function") or {}).get("arguments") or "")
               for m in a_state for tc in m.get("tool_calls") or []), "A lost its own memory"
    # ...but B's message reached A as a message, never B's tool trail
    a_user = "".join(m.get("content") or "" for m in a_state if m["role"] == "user")
    assert "Part two checks out" in a_user
    assert "print('b1')" not in a_user, "B's tool trail leaked to A"
    # ratify framing arrived (its own user message)
    assert prompts.RATIFY_REQUEST[:40] in a_user
    print("ok  test_propose_and_ratify")


def test_contest_once_then_accept():
    """B contests A's first proposal (work continues); after the contest budget is
    spent, the NEXT proposal stands without ratification."""
    script = [
        text_turn("Looked at it. FINAL ANSWER: 41"),             # A proposes (turn 1)
        text_turn("DECISION: contest\nThat misreads the source."),  # B contests (turn 2)
        text_turn("Rechecked. FINAL ANSWER: 42"),                # A proposes again (turn 3)
    ]
    c = FakeClient(script)
    r = run_dialogue("solve it", PY, c, "m", get_addon("vanilla"), t_max=8,
                     turn_budget=3, usd_budget=budget())
    assert r.contests == 1 and r.proposals == 2 and r.ratified is False
    assert "FINAL ANSWER: 42" in r.final
    assert r.turns_used == 3
    print("ok  test_contest_once_then_accept")


def test_turn_cap_forces_finalize():
    """No proposal by T=2: the turn-2 agent is forced to commit (or abstain)."""
    script = [
        text_turn("still working on part one"),                  # A turn 1 (no proposal)
        text_turn("me too, nothing solid yet"),                  # B turn 2 (cap reached)
        text_turn("FINAL ANSWER: UNKNOWN"),                      # B's forced commit
    ]
    c = FakeClient(script)
    r = run_dialogue("solve it", PY, c, "m", get_addon("vanilla"), t_max=2,
                     turn_budget=3, usd_budget=budget())
    assert r.final == "FINAL ANSWER: UNKNOWN" and r.committed
    assert r.turns_used == 2
    print("ok  test_turn_cap_forces_finalize")


def test_unusable_message_crosses_as_marker():
    """A turn whose message stays truncated crosses MESSAGE_MARKER, and the peer sees
    the marker — never the partial text (rule 6)."""
    script = [
        tool_turn(("run_python", {"code": "print(1)"})),         # A spends budget B=1
        text_turn("half a mess", finish="length"),               # msg attempt 1 (truncated)
        text_turn("still trunc", finish="length"),               # attempt 2
        text_turn("again trunc", finish="length"),               # attempt 3 -> marker
        text_turn("FINAL ANSWER: X"),                            # B (turn 2 = last) proposes
    ]
    c = FakeClient(script)
    r = run_dialogue("solve it", PY, c, "m", get_addon("vanilla"), t_max=2,
                     turn_budget=1, usd_budget=budget())
    assert r.messages[0] == prompts.MESSAGE_MARKER, r.messages
    b_user = "".join(m.get("content") or "" for m in r.states["peer_B"]
                     if m["role"] == "user")
    assert prompts.MESSAGE_MARKER in b_user and "half a mess" not in b_user
    assert "FINAL ANSWER: X" in r.final
    print("ok  test_unusable_message_crosses_as_marker")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nALL {len(fns)} DIALOGUE OFFLINE TESTS PASSED")
