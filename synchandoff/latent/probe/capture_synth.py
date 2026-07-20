"""Capture residual-stream activations for the v2 belief-strength probe.

For every synthetic snippet (gen_data.py), prefill it raw (no chat template —
the probe should read plain text, matching how it will scan A's templated
trace token stream) on the latent server, and pull hidden states at a few
positions in the belief-bearing tail region (default -1, -4, -7) at the
chosen middle layers, plus next-token entropy at the last position (reported
later as a correlation — NEVER trained on).

Run on piranha (tunnel to :8802 up):
  SYNCHANDOFF_LATENT_BASE=http://localhost:8802 \
  /tmp/aij2115/pyenv/bin/python -m latent.probe.capture_synth
Output: latent/probe/synth_captures.npz
  X_<layer>: [N*P, hidden], y, domain, cell, snippet_idx, tail_off, entropy
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from latent import client                            # noqa: E402

DATA = os.path.join(HERE, "synth_data.jsonl")
OUT = os.path.join(HERE, "synth_captures.npz")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layers", default="12,18,24")
    ap.add_argument("--positions", default="-1,-4,-7")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--save-every", type=int, default=200)
    args = ap.parse_args()
    layers = [int(x) for x in args.layers.split(",")]
    offs = [int(x) for x in args.positions.split(",")]

    rows = [json.loads(line) for line in open(DATA)]
    if args.limit:
        rows = rows[:args.limit]
    print(f"{len(rows)} snippets, layers {layers}, tail offsets {offs}")

    X = {lay: [] for lay in layers}
    y, dom, cell, sidx, toff, ent = [], [], [], [], [], []

    def save():
        arrs = {f"X_{lay}": np.asarray(X[lay], dtype=np.float32)
                for lay in layers}
        np.savez_compressed(
            OUT, y=np.asarray(y, dtype=np.int64),
            domain=np.asarray(dom), cell=np.asarray(cell),
            snippet_idx=np.asarray(sidx, dtype=np.int64),
            tail_off=np.asarray(toff, dtype=np.int64),
            entropy=np.asarray(ent, dtype=np.float32), **arrs)

    for i, row in enumerate(rows):
        try:
            r = client.prefill_capture(
                raw_text=row["text"], capture_layers=layers,
                return_entropy=True,
                return_hidden={"positions": offs, "layers": layers})
            client.session_free(r["session_id"])
        except Exception as e:
            print(f"  [{i}] ERROR {e}", flush=True)
            continue
        hid = r.get("hidden") or {}
        positions = hid.get("positions") or []
        for j, _pos in enumerate(positions):
            ok = all(str(lay) in hid["layers"] and
                     j < len(hid["layers"][str(lay)]) for lay in layers)
            if not ok:
                continue
            for lay in layers:
                X[lay].append(hid["layers"][str(lay)][j])
            y.append(row["label"])
            dom.append(row["domain"])
            cell.append(row["cell"])
            sidx.append(i)
            toff.append(offs[j] if j < len(offs) else 0)
            ent.append(r.get("last_entropy") or -1.0)
        if (i + 1) % args.save_every == 0:
            save()
            print(f"  {i+1}/{len(rows)} captured ({len(y)} samples)", flush=True)
    save()
    print(f"done: {len(y)} samples -> {OUT}")


if __name__ == "__main__":
    main()
