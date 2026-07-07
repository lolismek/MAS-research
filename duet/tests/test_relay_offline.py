"""Offline mechanics test for the agent primitive + relay — NO LLM, NO network.

A scripted fake OpenAI client returns a canned sequence of turns, so we can assert the
harness's control flow exactly: budget-forced hand-off, early finish, the repeated-action
loop guard, the truncation-marker edge guard, last-shift forced commit, and PDDL env
persistence across shifts (via a mock env). Tool calls use `run_python` (local subprocess,
deterministic) so no benchmark network is touched.

Run:  conda run -n autogen_gc python duet/tests/test_relay_offline.py
"""
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "harness"))

import prompts
from agent import run_agent, Budget, _STUB_PREFIX, PROXY_TRUNCATION_SENTINEL
from relay import run_relay
from arms import get_addon

# --- a scripted fake OpenAI client -------------------------------------------
_TC_ID = [0]


class _Fn:
    def __init__(self, name, args): self.name, self.arguments = name, args


class _TC:
    def __init__(self, name, args):
        _TC_ID[0] += 1
        self.id, self.type, self.function = f"tc{_TC_ID[0]}", "function", _Fn(name, args)


class _Msg:
    def __init__(self, content, tool_calls): self.content, self.tool_calls = content, tool_calls


class _Choice:
    def __init__(self, msg, fr): self.message, self.finish_reason = msg, fr


class _Usage:
    prompt_tokens, completion_tokens = 100, 50


class _Resp:
    def __init__(self, msg, fr): self.choices, self.usage = [_Choice(msg, fr)], _Usage()


def tool_turn(*calls):
    """calls: (name, args_dict) pairs -> one assistant turn requesting those tools."""
    return _Resp(_Msg(None, [_TC(n, json.dumps(a)) for n, a in calls]), "tool_calls")


def text_turn(content, finish="stop"):
    return _Resp(_Msg(content, None), finish)


class _Completions:
    def __init__(self, outer): self.outer = outer

    def create(self, **kw):
        self.outer.calls.append(kw)
        assert self.outer.script, "fake client ran out of scripted turns"
        return self.outer.script.pop(0)


class _Chat:
    def __init__(self, outer): self.completions = _Completions(outer)


class FakeClient:
    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.chat = _Chat(self)


def budget():
    return Budget(10.0, 0.36, 0.89)


PY = ["run_python"]


# --- tests -------------------------------------------------------------------
def test_budget_forces_handoff_and_commit():
    """3-shift relay, B=3: each of shifts 1&2 spends its budget and hands off; shift 3
    spends its budget then is force-committed. Assert 3 shifts, 2 notes crossed, the
    committed final answer, and that successors actually received the notes."""
    script = [
        tool_turn(("run_python", {"code": "print(1)"})),   # shift 1: 3 varied tool calls
        tool_turn(("run_python", {"code": "print(2)"})),
        tool_turn(("run_python", {"code": "print(3)"})),
        text_turn("NOTE ONE: established A; open B."),      # shift 1 hand-off note
        tool_turn(("run_python", {"code": "print(4)"})),    # shift 2: 3 varied tool calls
        tool_turn(("run_python", {"code": "print(5)"})),
        tool_turn(("run_python", {"code": "print(6)"})),
        text_turn("NOTE TWO: confirmed A; still open B."),  # shift 2 hand-off note
        tool_turn(("run_python", {"code": "print(7)"})),    # shift 3: 3 varied tool calls
        tool_turn(("run_python", {"code": "print(8)"})),
        tool_turn(("run_python", {"code": "print(9)"})),
        text_turn("FINAL ANSWER: 42"),                      # shift 3 forced commit
    ]
    c = FakeClient(script)
    r = run_relay("solve it", PY, c, "m", get_addon("vanilla"), k=3, tool_budget=3, usd_budget=budget())
    assert r.shifts_used == 3, r.shifts_used
    assert r.notes == ["NOTE ONE: established A; open B.", "NOTE TWO: confirmed A; still open B."], r.notes
    assert r.final == "FINAL ANSWER: 42", r.final
    assert r.committed is True
    assert [s.finish for s in r.shifts] == ["stop", "stop", "stop"]   # each ends on its note/commit
    # successor context actually contained the predecessor's note (framed), not the transcript
    joined = "".join(m.get("content") or "" for m in r.shifts[1].transcript if m["role"] == "user")
    assert "NOTE ONE" in joined and prompts.SUCCESSOR_PREAMBLE[:30] in joined, "note not delivered to successor"
    assert "print(1)" not in joined, "predecessor TRANSCRIPT leaked across the edge (should be note-only)"
    print("ok  test_budget_forces_handoff_and_commit  shifts=3 notes=2 final=42")


def test_early_finish_ends_relay():
    """Shift 1 commits immediately -> relay ends at shift 1, no hand-off (mechanic 1)."""
    c = FakeClient([text_turn("FINAL ANSWER: done")])
    r = run_relay("solve it", PY, c, "m", get_addon("vanilla"), k=3, tool_budget=3, usd_budget=budget())
    assert r.shifts_used == 1 and r.notes == [] and r.final == "FINAL ANSWER: done", (r.shifts_used, r.notes)
    assert r.committed is True
    print("ok  test_early_finish_ends_relay  shifts=1")


def test_loop_guard_trips_on_repeats():
    """Identical (tool,args) REPEAT_LIMIT times -> forced stop 'loop' even with budget spare
    (B set high so the loop guard, not the budget, is what fires)."""
    script = [
        tool_turn(("run_python", {"code": "print(1)"})),   # same call 3x -> loop guard
        tool_turn(("run_python", {"code": "print(1)"})),
        tool_turn(("run_python", {"code": "print(1)"})),
        text_turn("HANDOFF after loop"),                   # the hand-off continuation
    ]
    c = FakeClient(script)
    res = run_agent("shift_1", prompts.SOLVER_SYS, [{"role": "user", "content": "go"}], PY,
                    c, "m", get_addon("vanilla"), tool_budget=99, usd_budget=budget())
    assert res.finish == "loop", res.finish
    assert res.n_tool_calls == 3, res.n_tool_calls
    print("ok  test_loop_guard_trips_on_repeats  finish=loop tools=3")


def test_truncated_note_becomes_marker():
    """A hand-off note that stays cut off (finish_reason 'length') across EVERY retry must
    NOT cross the edge; the TRUNCATED_MARKER does instead (hygiene rule 6). A single 'length'
    now triggers a nudge-retry, so persistent truncation is needed to reach the marker."""
    script = [
        tool_turn(("run_python", {"code": "print(1)"})),
        tool_turn(("run_python", {"code": "print(2)"})),
        text_turn("this note was cut off mid-sen", finish="length"),   # attempt 1: truncated
        text_turn("still spiralling, cut off", finish="length"),       # attempt 2 (post-nudge): truncated
        text_turn("and truncated once more", finish="length"),         # attempt 3 (post-nudge): truncated
        text_turn("FINAL ANSWER: X"),                                  # shift 2 commit (early)
    ]
    c = FakeClient(script)
    r = run_relay("solve it", PY, c, "m", get_addon("vanilla"), k=2, tool_budget=2, usd_budget=budget())
    assert r.notes == [prompts.TRUNCATED_MARKER], r.notes
    joined = "".join(m.get("content") or "" for m in r.shifts[1].transcript if m["role"] == "user")
    assert prompts.TRUNCATED_MARKER in joined and "cut off mid-sen" not in joined
    print("ok  test_truncated_note_becomes_marker  marker crossed after 3 truncated tries")


def test_sentinel_wrapup_reasks_for_plaintext():
    """The proxy replaces a think-truncated reply with a NON-empty sentinel string. A naive
    'retry only when empty' guard would cross it as the note; instead it must be treated as
    no-output and re-asked (the bug that caused gaia_983bba7c's markers)."""
    script = [
        tool_turn(("run_python", {"code": "print(1)"})),   # shift 1: spend B=2
        tool_turn(("run_python", {"code": "print(2)"})),
        text_turn(PROXY_TRUNCATION_SENTINEL, finish="length"),   # attempt 1: spiralled think -> sentinel
        text_turn("RECOVERED NOTE after nudge"),                 # attempt 2 (post-nudge): the real note
        text_turn("FINAL ANSWER: S"),                            # shift 2 early finish
    ]
    c = FakeClient(script)
    r = run_relay("solve it", PY, c, "m", get_addon("vanilla"), k=2, tool_budget=2, usd_budget=budget())
    assert r.notes == ["RECOVERED NOTE after nudge"], r.notes
    assert PROXY_TRUNCATION_SENTINEL not in r.notes[0]
    assert r.final == "FINAL ANSWER: S"
    print("ok  test_sentinel_wrapup_reasks_for_plaintext  sentinel not mistaken for a note")


def test_wrapup_compacts_tool_dumps():
    """Before a wrap-up, raw tool dumps are stubbed (except the freshest) so the reflective
    ask can't spiral over them; the note is written from memory (the gaia_983bba7c fix)."""
    # Use computed outputs (7*6=42, 8*9=72) so the OUTPUT value is absent from the call args:
    # a stub keeps the args as a re-fetchable label, so asserting on the output proves the
    # raw result body was elided, not merely that the code string differs.
    script = [
        tool_turn(("run_python", {"code": "print(7*6)"})),     # tool result 0 (output '42') -> stubbed
        tool_turn(("run_python", {"code": "print(8*9)"})),     # tool result 1 (output '72', freshest) -> kept
        text_turn("NOTE: from memory"),                        # hand-off note (clean)
        text_turn("FINAL ANSWER: ok"),                         # shift 2 early finish
    ]
    c = FakeClient(script)
    r = run_relay("solve it", PY, c, "m", get_addon("vanilla"), k=2, tool_budget=2, usd_budget=budget())
    tool_msgs = [m for m in r.shifts[0].transcript if m["role"] == "tool"]
    assert len(tool_msgs) == 2, tool_msgs
    assert tool_msgs[0]["content"].startswith(_STUB_PREFIX), "old tool dump not compacted before wrap-up"
    assert "42" not in tool_msgs[0]["content"], "raw output survived compaction"
    assert not tool_msgs[1]["content"].startswith(_STUB_PREFIX), "freshest tool result should be kept whole"
    assert "72" in tool_msgs[1]["content"], "freshest evidence lost"
    assert r.notes == ["NOTE: from memory"]
    print("ok  test_wrapup_compacts_tool_dumps  old dumps stubbed, freshest kept")


def test_empty_wrapup_reasks_for_plaintext():
    """A shift cut off mid-work replies to the hand-off request with a tool-call (empty
    visible content); continue_agent must re-ask firmly and get the real note (the empty
    turn is dropped, not crossed)."""
    script = [
        tool_turn(("run_python", {"code": "print(1)"})),   # shift 1: spend B=2
        tool_turn(("run_python", {"code": "print(2)"})),
        tool_turn(("run_python", {"code": "print(9)"})),   # HANDOFF attempt 1: tool-call, empty text
        text_turn("REAL NOTE after nudge"),                # HANDOFF attempt 2 (post-nudge): the note
        text_turn("FINAL ANSWER: Z"),                      # shift 2 early finish
    ]
    c = FakeClient(script)
    r = run_relay("solve it", PY, c, "m", get_addon("vanilla"), k=2, tool_budget=2, usd_budget=budget())
    assert r.notes == ["REAL NOTE after nudge"], r.notes
    joined = "".join(m.get("content") or "" for m in r.shifts[1].transcript if m["role"] == "user")
    assert "REAL NOTE after nudge" in joined
    assert r.final == "FINAL ANSWER: Z"
    print("ok  test_empty_wrapup_reasks_for_plaintext  nudge recovered the note")


def test_all_empty_wrapup_falls_back_to_marker():
    """If every wrap-up attempt is empty (model keeps tool-calling), no blank crosses the
    edge — the marker does (rule 6)."""
    script = [
        tool_turn(("run_python", {"code": "print(1)"})),   # shift 1: spend B=2
        tool_turn(("run_python", {"code": "print(2)"})),
        tool_turn(("run_python", {"code": "print(3)"})),   # HANDOFF attempt 1 (empty)
        tool_turn(("run_python", {"code": "print(4)"})),   # attempt 2 after nudge (empty)
        tool_turn(("run_python", {"code": "print(5)"})),   # attempt 3 after nudge (empty)
        text_turn("FINAL ANSWER: Q"),                      # shift 2 early finish
    ]
    c = FakeClient(script)
    r = run_relay("solve it", PY, c, "m", get_addon("vanilla"), k=2, tool_budget=2, usd_budget=budget())
    assert r.notes == [prompts.TRUNCATED_MARKER], r.notes
    assert r.final == "FINAL ANSWER: Q"
    print("ok  test_all_empty_wrapup_falls_back_to_marker  marker crossed after 3 empty tries")


def test_no_final_line_retry():
    """Last shift's forced commit slips the format (no 'FINAL ANSWER:' line, clean stop) ->
    one constrained retry recovers it."""
    script = [
        text_turn("I think the answer is probably 7 but I'm not writing the line"),  # shift1: no tools, no line
        text_turn("still no line, just prose"),        # FINAL_COMMIT_REQUEST reply (no line)
        text_turn("FINAL ANSWER: 7"),                  # NO_FINAL_RETRY reply
    ]
    c = FakeClient(script)
    # k=1 so shift 1 IS the last shift; it stops clean without a line -> commit path.
    r = run_relay("solve it", PY, c, "m", get_addon("vanilla"), k=1, tool_budget=3, usd_budget=budget())
    assert r.final == "FINAL ANSWER: 7", r.final
    assert r.committed is True
    print("ok  test_no_final_line_retry  recovered FINAL ANSWER via retry")


def test_env_persists_across_shifts():
    """The SAME world object is threaded through every shift (mechanic 5): a mock env's
    step counter accumulates across shift 1 and shift 2. Only 'pddl_step' bills the budget."""
    class MockEnv:
        def __init__(self): self.steps = 0; self.seen = []

        def run_tool(self, name, arg):
            if name == "pddl_step":
                self.steps += 1; self.seen.append(arg); return f"Applied {arg}. step {self.steps}"
            return "obs: some facts"

        def goal_reached(self): return self.steps >= 4

    env = MockEnv()
    tools = ["pddl_observe", "pddl_actions", "pddl_step"]
    script = [
        tool_turn(("pddl_observe", {})),                       # free lookup (doesn't bill B)
        tool_turn(("pddl_step", {"action": "pick a"})),        # env step 1 (bills)
        tool_turn(("pddl_step", {"action": "stack a b"})),     # env step 2 (bills) -> B=2 hit
        text_turn("world: a on b; open: c"),                   # shift 1 note
        tool_turn(("pddl_step", {"action": "pick c"})),        # env step 3
        tool_turn(("pddl_step", {"action": "stack c a"})),     # env step 4 -> B=2 hit
        text_turn("FINAL ANSWER: DONE"),                       # shift 2 forced commit
    ]
    c = FakeClient(script)
    r = run_relay("plan it", tools, c, "m", get_addon("vanilla"), k=2, tool_budget=2,
                  budget_tool_names={"pddl_step"}, usd_budget=budget(), env=env)
    assert env.steps == 4, f"env did not persist across shifts: steps={env.steps}"
    assert env.seen == ["pick a", "stack a b", "pick c", "stack c a"], env.seen
    assert r.shifts_used == 2 and r.final == "FINAL ANSWER: DONE"
    print("ok  test_env_persists_across_shifts  env.steps=4 across 2 shifts")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nALL {len(fns)} OFFLINE TESTS PASSED")
