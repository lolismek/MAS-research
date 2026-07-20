"""L-PROBE artifact builder: vanilla note + probe-decoded epistemic annex.

The annex is text INSIDE the W budget (capacity-fair by construction): probe
probabilities read from A's residual stream at the end of A's final turn.
lprobe_shuffled uses the shuffled-coefficient twin probes (label-destroying
control at identical prompt shape).

Needs: latent/probe/probes.json (train.py) + the latent server (activation
capture at build time).
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROBES_F = os.path.join(HERE, "probes.json")

DESCR = {
    "located_file": "predecessor had found the defective file",
    "seen_func": "predecessor had seen the defective function",
    "solved": "repository was already fixed by the predecessor",
}

ANNEX_HEADER = (
    "PROBE ANNEX — read-outs decoded directly from your predecessor's "
    "internal state (calibrated on held-out tasks; independent of the note "
    "above):")


def _score(probe, h):
    x = (np.asarray(h) - np.asarray(probe["mu"])) / np.asarray(probe["sd"])
    z = float(np.dot(x, np.asarray(probe["coef"])) + probe["intercept"])
    return 1.0 / (1.0 + math.exp(-z))


def build_lprobe(arm, frozen, instance):
    from handoff.arms import events_to_messages, truncate_to_budget, W_HARD_CHARS
    from harness.agent import TOOL_SPECS
    from handoff.latent_arms import _load_note
    from latent import client

    if not os.path.exists(PROBES_F):
        raise RuntimeError("latent/probe/probes.json missing — run the "
                           "capture + train pipeline first (see probe/README)")
    with open(PROBES_F) as f:
        allp = json.load(f)
    probes = allp["shuffled"] if arm == "lprobe_shuffled" else allp["probes"]

    iid = instance["instance_id"]
    k = frozen["meta"]["k"]
    layers = sorted({p["layer"] for p in probes.values()})
    r = client.prefill_capture(
        messages=events_to_messages(frozen["events"]), tools=TOOL_SPECS,
        capture_layers=layers,
        return_hidden={"positions": "turn_ends:assistant", "layers": layers})
    client.session_free(r["session_id"])
    hid = r.get("hidden") or {}

    lines = [ANNEX_HEADER]
    aux = {"arm": arm, "k": k, "scores": {}, "probe_cv": {}}
    for label, p in probes.items():
        states = hid["layers"].get(str(p["layer"]))
        if not states:
            continue
        s = _score(p, states[-1])
        aux["scores"][label] = round(s, 3)
        aux["probe_cv"][label] = {"cv_acc": p.get("cv_acc"),
                                  "cv_auc": p.get("cv_auc")}
        lines.append(f"- P({DESCR.get(label, label)}) = {s:.2f}")
    annex = "\n".join(lines)

    note = _load_note(iid, k)
    # annex is part of the W budget: budget the note to leave room for it
    room = max(200, W_HARD_CHARS - len(annex) - 2)
    body = truncate_to_budget(note, hard_chars=room) + "\n\n" + annex
    aux["slot_unit"] = "text_token_within_W"
    return truncate_to_budget(body), aux
