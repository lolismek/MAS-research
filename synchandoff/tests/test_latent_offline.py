"""Offline unit tests for the latent-arm plumbing — no server, no GPU. Run:
    python -m pytest tests/test_latent_offline.py -q     (from synchandoff/)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handoff.arms import ARMS, LATENT_ARMS, BOARD_FAMILY
from handoff import latent_arms as LA
from latent.probe import labels as L


MARKER_RE = re.compile(r"\[\[LATENT:(kv|embeds):([A-Za-z0-9_\-\.]+)\]\]")


def test_latent_arm_lists_consistent():
    assert set(LA.LATENT_ARMS) == set(LATENT_ARMS)
    assert not set(LATENT_ARMS) & set(ARMS)
    assert not set(LATENT_ARMS) & BOARD_FAMILY
    # v2 KV arm -> server-arm mapping, all at slot parity n=W
    assert LA.KV_ARMS == {"lkv_attn": "kv_attn", "lkv_last": "kv_last",
                          "lkv_rand": "kv_rand"}
    assert LA.W_SLOTS == 300


def test_marker_roundtrip():
    txt = LA._artifact_text("kv", LA._aid("lkv_attn", "x" * 100, 12))
    m = MARKER_RE.search(txt)
    assert m and m.group(1) == "kv"
    assert m.group(2).startswith("lkv_attn__")
    # carrier text identical across arms/kinds (prompt-confound control)
    t2 = LA._artifact_text("embeds", "lthought_soft__abc__k12")
    assert MARKER_RE.sub("", txt).strip() == MARKER_RE.sub("", t2).strip()


def test_seed_deterministic():
    assert LA._seed("foo") == LA._seed("foo")
    assert LA._seed("foo") != LA._seed("bar")


def _events(instance):
    return [
        {"type": "system", "content": "sys"},
        {"type": "user", "content": "task"},
        {"type": "assistant", "content": "let me look around",
         "tool_calls": [{"name": "bash", "arguments": json.dumps(
             {"command": "ls src/"})}]},
        {"type": "tool", "name": "bash", "arguments": {"command": "ls src/"},
         "result": "core.py\nutil.py"},
        {"type": "assistant", "content": "reading the suspicious file",
         "tool_calls": [{"name": "read_file", "arguments": json.dumps(
             {"path": "src/core.py"})}]},
        {"type": "tool", "name": "read_file",
         "arguments": {"path": "src/core.py"},
         "result": "def frobnicate():\n    pass"},
        {"type": "assistant", "content": "frobnicate looks stale"},
    ]


def test_turn_labels_cumulative():
    inst = {"pyfile_path": "/x/test_repo/src/core.py", "fm_name": "frobnicate"}
    labels = L.turn_labels(_events(inst), inst)
    assert len(labels) == 3
    assert labels[0] == {"located_file": False, "seen_func": False}
    # turn 2's own tool call names the gold file, but the function name only
    # appears in the RESULT, which lands AFTER turn 2's captured position
    assert labels[1] == {"located_file": True, "seen_func": False}
    assert labels[2] == {"located_file": True, "seen_func": True}


def test_final_labels():
    inst = {"pyfile_path": "/x/test_repo/src/core.py", "fm_name": "frobnicate"}
    fin = L.final_labels(_events(inst), {"post_A_solved": False}, inst)
    assert fin == {"solved": False, "located_file": True, "seen_func": True}
