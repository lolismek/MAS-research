"""Latent handoff arms (L-KV, L-THOUGHT + controls) — piranha-side builders.

Each builder returns (artifact_text, aux) like the text arms, but the
artifact TEXT is only a carrier: a `[[LATENT:<kind>:<artifact_id>]]` marker
plus one fixed sentence (identical across all latent arms and controls, so
the text channel is prompt-confound-free). The actual payload lives on the
latent server (tigerfish, /tmp/aij2115/latent_artifacts) and is injected into
B's forward pass when the marker reaches the server through the latent proxy
chain (see infra/README.md).

| condition     | latent payload                                              |
|---------------|-------------------------------------------------------------|
| lkv           | KV of the LAST n=300 positions of A's re-prefilled context  |
| lkv_n75       | same, n=75  (capacity sweep W/4)                            |
| lkv_n19       | same, n=19  (capacity sweep W/16)                           |
| lkv_rand      | KV of n=300 RANDOM positions (position-selection control)   |
| lkv_notekv    | KV of the vanilla NOTE's text (channel control: mechanically |
|               | identical injection, text-limited content)                  |
| lthought      | m=32 training-free Coconut/LatentMAS latent thoughts        |
| lthought_rand | m=32 random vectors, per-vector norm matched to lthought    |
| lthought_pool | m=32 mean-pooled token embeddings of the vanilla note       |
|               | (content-matched, mechanism-latent control; the designated  |
|               | fallback primary if coconut thoughts collapse)              |

Slot/bit capacity ledgers are recorded by the server into each artifact's
aux (returned here and saved as <arm>.json by build_artifacts).

Build-order dependencies (within an instance): `vanilla` must exist before
lkv_notekv / lthought_pool (they read its note); lthought_rand builds (or
reuses) lthought's artifact as its norm reference.
"""
import hashlib
import os

from latent import client

W_SLOTS = 300                    # slot parity with the W_SOFT text budget
KV_SWEEP = {"lkv": W_SLOTS, "lkv_n75": 75, "lkv_n19": 19}
LATENT_ARMS = ["lkv", "lkv_n75", "lkv_n19", "lkv_rand", "lkv_notekv",
               "lthought", "lthought_rand", "lthought_pool",
               "lprobe", "lprobe_shuffled"]
THOUGHT_M = 32

CARRIER_TEXT = (
    "(Attached to this note is your predecessor's working memory in a "
    "latent, non-textual form. You cannot read it as text, but it may prime "
    "what you recall about this task.)")

LATENT_SUMMARY_REQUEST = (
    "You have reached the end of your available time on this task, so you "
    "must stop working now. Another worker will continue from where you left "
    "off. Summarize for them everything useful you have established: what "
    "you found (with the evidence), what the cause of the failure seems to "
    "be, what you ruled out, and what you would try next."
)

HERE = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS = os.path.join(os.path.dirname(HERE), "artifacts")

_SESS = {}                      # (iid, k, kind) -> session_id (server keeps 2)


def _artifact_text(kind, aid):
    return f"[[LATENT:{kind}:{aid}]]\n{CARRIER_TEXT}"


def _seed(iid):
    return int(hashlib.sha1(iid.encode()).hexdigest()[:8], 16)


def _load_note(iid, k):
    p = os.path.join(ARTIFACTS, iid, f"plain_k{k}", "vanilla.txt")
    with open(p) as f:
        note = f.read().strip()
    if not note:
        raise RuntimeError(f"empty vanilla note for {iid} (build vanilla first)")
    return note


def _messages_and_tools(events):
    # late import: harness.agent pulls no heavy deps, but keep the seam thin
    from handoff.arms import events_to_messages
    from harness.agent import TOOL_SPECS
    return events_to_messages(events), TOOL_SPECS


def _get_session(events, iid, k, kind):
    """kind: 'traj' (A's transcript as-is) | 'thought' (transcript + summary
    request + generation prompt) | note sessions are built inline."""
    key = (iid, k, kind)
    if key in _SESS:
        return _SESS[key]
    messages, tools = _messages_and_tools(events)
    if kind == "thought":
        messages = messages + [{"role": "user", "content": LATENT_SUMMARY_REQUEST}]
    r = client.prefill_capture(messages=messages, tools=tools,
                               add_generation_prompt=(kind == "thought"))
    _SESS[key] = r["session_id"]
    return r["session_id"]


def _make_with_session(events, iid, k, kind, arm, params, aid):
    """make_artifact with one retry if the memoized session was evicted."""
    import requests as _rq
    sid = _get_session(events, iid, k, kind)
    try:
        return client.make_artifact(arm, sid, params, artifact_id=aid)
    except _rq.HTTPError as e:
        if e.response is not None and e.response.status_code == 400:
            _SESS.pop((iid, k, kind), None)
            sid = _get_session(events, iid, k, kind)
            return client.make_artifact(arm, sid, params, artifact_id=aid)
        raise


def _aid(arm, iid, k):
    return f"{arm}__{iid[:80]}__k{k}"


def _build_lthought(events, iid, k):
    aid = _aid("lthought", iid, k)
    aux = _make_with_session(events, iid, k, "thought", "thought_coconut",
                             {"m": THOUGHT_M, "rescale": True}, aid)
    return aid, aux


def build(arm, frozen, instance):
    """Mirror of arms.build_artifact for the latent conditions."""
    iid = instance["instance_id"]
    events = frozen["events"]
    k = frozen["meta"]["k"]
    aid = _aid(arm, iid, k)

    if arm in KV_SWEEP:
        aux = _make_with_session(events, iid, k, "traj", "kv_last",
                                 {"n": KV_SWEEP[arm]}, aid)
        return _artifact_text("kv", aid), aux
    if arm == "lkv_rand":
        aux = _make_with_session(events, iid, k, "traj", "kv_rand",
                                 {"n": W_SLOTS, "seed": _seed(iid)}, aid)
        return _artifact_text("kv", aid), aux
    if arm == "lkv_notekv":
        note = _load_note(iid, k)
        r = client.prefill_capture(raw_text=note)
        aux = client.make_artifact("kv_last", r["session_id"],
                                   {"n": r["n_tokens"]}, artifact_id=aid)
        client.session_free(r["session_id"])
        return _artifact_text("kv", aid), aux
    if arm == "lthought":
        _, aux = _build_lthought(events, iid, k)
        return _artifact_text("embeds", aid), aux
    if arm == "lthought_rand":
        ref_aid, _ = _build_lthought(events, iid, k)
        aux = client.make_artifact("thought_rand", None,
                                   {"ref_artifact_id": ref_aid,
                                    "seed": _seed(iid)}, artifact_id=aid)
        return _artifact_text("embeds", aid), aux
    if arm == "lthought_pool":
        note = _load_note(iid, k)
        aux = client.make_artifact("thought_pool", None,
                                   {"m": THOUGHT_M, "text": note},
                                   artifact_id=aid)
        return _artifact_text("embeds", aid), aux
    if arm in ("lprobe", "lprobe_shuffled"):
        from latent.probe import annex
        return annex.build_lprobe(arm, frozen, instance)
    raise KeyError(f"unknown latent arm {arm!r}; have {LATENT_ARMS}")
