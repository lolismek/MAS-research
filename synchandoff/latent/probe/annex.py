"""L-PROBE v2 artifact builder: belief-strength peaks -> windows -> summary.

Per PLAN_V2: score every position of A's frozen trace with the task-agnostic
belief-strength probe -> peak-pick (NMS, min separation) top-P peaks ->
±window-token excerpts -> ONE vLLM summarizer call ("these are the moments
the agent held strong beliefs; summarize what it believed") -> W-budget note
= the artifact. Controls:
  lprobe_randsel   same NUMBER of windows at random positions (same min-sep),
                   same summarizer — isolates the probe's SELECTION value
  lprobe_shuffled  shuffled probe weights end-to-end (selection AND scores)

Needs: latent/probe/probes.json (train.py) + the latent server (trace
capture at build time) + the vLLM proxy for the summarizer call.
"""
import hashlib
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
PROBES_F = os.path.join(HERE, "probes.json")

N_PEAKS = 6
MIN_SEP = 300
WINDOW = 150

SUMMARIZER_PROMPT = (
    "A predecessor agent worked on a software task and ran out of time. "
    "Below are short excerpts from the exact moments in its work session "
    "where it held its strongest beliefs about what was happening (excerpts "
    "are raw transcript fragments and may start/end mid-line).\n\n{windows}\n\n"
    "Summarize, as a plain-text handoff note of at most {soft} tokens for the "
    "worker taking over, what the predecessor believed at these moments: what "
    "it thought the problem was, where, and what it was about to do. Report "
    "beliefs faithfully even if they might be wrong. Do not invent details "
    "that are not supported by the excerpts.")

_SESS = {}       # (iid, k) -> (session_id, n_tokens); server keeps 2 sessions


def _get_session(frozen, iid, k, layer):
    from handoff.arms import events_to_messages
    from harness.agent import TOOL_SPECS
    from latent import client
    key = (iid, k)
    if key in _SESS:
        return _SESS[key]
    r = client.prefill_capture(messages=events_to_messages(frozen["events"]),
                               tools=TOOL_SPECS, capture_layers=[layer])
    _SESS[key] = (r["session_id"], r["n_tokens"])
    return _SESS[key]


def _rand_positions(iid, n_tokens, n, min_sep, seed_tag=""):
    rng = random.Random(int(hashlib.sha1(
        (iid + seed_tag).encode()).hexdigest()[:8], 16))
    picks = []
    for _ in range(4000):
        if len(picks) >= n:
            break
        p = rng.randrange(0, n_tokens)
        if all(abs(p - q) >= min_sep for q in picks):
            picks.append(p)
    return sorted(picks)


def build_lprobe(arm, frozen, instance):
    from handoff.arms import truncate_to_budget, W_SOFT_TOKENS
    from harness import llm
    from latent import client

    if not os.path.exists(PROBES_F):
        raise RuntimeError("latent/probe/probes.json missing — run the "
                           "gen_data/capture_synth/train pipeline first")
    with open(PROBES_F) as f:
        allp = json.load(f)
    probe = allp["shuffled"] if arm == "lprobe_shuffled" else allp["belief_strength"]
    layer = probe["layer"]

    iid = instance["instance_id"]
    k = frozen["meta"]["k"]
    sid, n_tokens = _get_session(frozen, iid, k, layer)

    positions = None
    if arm == "lprobe_randsel":
        positions = _rand_positions(iid, n_tokens, N_PEAKS, MIN_SEP)
    try:
        r = client.probe_score(sid, layer, probe, n_peaks=N_PEAKS,
                               min_sep=MIN_SEP, window=WINDOW,
                               positions=positions)
    except Exception:
        # evicted session: rebuild once
        _SESS.pop((iid, k), None)
        sid, n_tokens = _get_session(frozen, iid, k, layer)
        if arm == "lprobe_randsel":
            positions = _rand_positions(iid, n_tokens, N_PEAKS, MIN_SEP)
        r = client.probe_score(sid, layer, probe, n_peaks=N_PEAKS,
                               min_sep=MIN_SEP, window=WINDOW,
                               positions=positions)

    wtexts = "\n\n".join(
        f"--- excerpt {i+1} (belief strength {w['score']:.2f}) ---\n{w['text']}"
        for i, w in enumerate(r["windows"]))
    msg = llm.chat([{"role": "user", "content": SUMMARIZER_PROMPT.format(
        windows=wtexts, soft=W_SOFT_TOKENS)}], max_tokens=1200,
        tag=f"lprobe_sum:{arm}:{iid}")
    note = truncate_to_budget((msg.get("content") or "").strip())

    aux = {"arm": arm, "k": k, "layer": layer, "n_tokens": n_tokens,
           "selection": "random" if arm == "lprobe_randsel" else "probe_nms",
           "peaks": r["peaks"], "curve_mean": r.get("curve_mean"),
           "curve_std": r.get("curve_std"), "curve_q90": r.get("curve_q90"),
           "probe_val_acc": probe.get("val_acc"),
           "slot_unit": "text_token_within_W",
           "summarizer_usage": msg.get("_usage")}
    return note, aux
