"""Capture residual-stream activations for L-PROBE.

For every frozen phase-1 trajectory (a candidates file + phase1_frozen/), re-
prefill A's transcript on the latent server and pull the hidden states at the
END of each assistant turn, at the chosen (middle) layers. Saves one .npz per
instance plus labels.

Run on piranha (tunnel to :8802 up):
  SYNCHANDOFF_LATENT_BASE=http://localhost:8802 \
  /tmp/aij2115/pyenv/bin/python -m latent.probe.capture \
      --candidates train_candidates.json --k 12 --layers 20,26,32
Output: latent/probe/captures/<iid>.npz  {h_<layer>: [P,2048], meta json}
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))       # synchandoff/
sys.path.insert(0, ROOT)

from handoff.arms import events_to_messages          # noqa: E402
from harness.agent import TOOL_SPECS                 # noqa: E402
from latent import client                            # noqa: E402
from latent.probe import labels as L                 # noqa: E402

CAPTURES = os.path.join(HERE, "captures")
FROZEN = os.path.join(ROOT, "phase1_frozen")


def load_frozen(iid, k, family="plain"):
    d = os.path.join(FROZEN, iid, f"{family}_k{k}")
    if not os.path.exists(os.path.join(d, "meta.json")):
        return None
    with open(os.path.join(d, "meta.json")) as f:
        meta = json.load(f)
    events = []
    with open(os.path.join(d, "traj.jsonl")) as f:
        for line in f:
            events.append(json.loads(line))
    return {"events": events, "meta": meta}


def capture_one(inst, k, layers):
    iid = inst["instance_id"]
    out_f = os.path.join(CAPTURES, f"{iid}.npz")
    if os.path.exists(out_f):
        return "skip"
    frozen = load_frozen(iid, k)
    if frozen is None:
        return "missing_frozen"
    events = frozen["events"]
    messages = events_to_messages(events)
    r = client.prefill_capture(
        messages=messages, tools=TOOL_SPECS, capture_layers=layers,
        return_hidden={"positions": "turn_ends:assistant", "layers": layers})
    client.session_free(r["session_id"])
    hid = r.get("hidden") or {}
    positions = hid.get("positions") or []
    per_turn = L.turn_labels(events, inst)
    fin = L.final_labels(events, frozen["meta"], inst)
    n = min(len(positions), len(per_turn))
    arrs = {}
    for lay in layers:
        m = hid["layers"].get(str(lay))
        if not m:
            return "no_hidden"
        arrs[f"h_{lay}"] = np.asarray(m, dtype=np.float32)[:n]
    meta = {
        "instance_id": iid, "k": k, "n_tokens": r["n_tokens"],
        "positions": positions[:n],
        "repo": iid.split("_callee")[0],
        "turn_labels": per_turn[:n],
        "final_labels": fin,
    }
    os.makedirs(CAPTURES, exist_ok=True)
    np.savez_compressed(out_f, meta=json.dumps(meta), **arrs)
    return f"ok ({n} positions, {r['n_tokens']} tokens)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--k", type=int, default=12)
    ap.add_argument("--layers", default="20,26,32")
    ap.add_argument("--split", default="callee")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    layers = [int(x) for x in args.layers.split(",")]

    from harness import instances as I
    by_id = {i["instance_id"]: i for i in I.load_instances(args.split)}
    with open(args.candidates) as f:
        cands = json.load(f)
    ids = [c["instance_id"] if isinstance(c, dict) else c for c in cands]
    if args.limit:
        ids = ids[:args.limit]
    for iid in ids:
        inst = by_id.get(iid)
        if inst is None:
            print(f"  [?] {iid[:60]}: not in split")
            continue
        try:
            status = capture_one(inst, args.k, layers)
        except Exception as e:
            status = f"ERROR {e}"
        print(f"  [{status}] {iid[:70]}", flush=True)


if __name__ == "__main__":
    main()
