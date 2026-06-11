"""Arm-3/4 payload capture: re-forward A's note turn, harvest states.

Run:  python -m probe.capture.run_capture ...          # notes + arm-2 latents first
      python -m probe.capture.capture_payloads --model full --run main --limit 38

Reads the notes an existing capture run generated (byte-identical reuse — the
new payloads pair with that run's arms 1/2/5 outputs) and, per context:
1. Rebuild A's exact prompt and re-forward it (prompt with use_cache, then
   note tokens against the cache) under EAGER attention — explicit scores
   only for the note turn, per the plan's implementation notes.
2. Arm-3 payload: A's last-layer states for the note's own tokens,
   norm-matched (per-layer raw states stored too, for a later level (ii)).
3. Arm-4 payload: last-layer states of the top-k_max transcript positions
   ranked by the attention the note tokens place on them (sink-masked,
   mid-to-late layers, max over heads). Arms runner subsets to k at use time.

Outputs under runs/<run>/capture/:
  <ctx>_payloads.safetensors   arm3_suffix_states [n_note, hidden] (fp32),
                               arm3_suffix_per_layer [L+1, n_note, hidden] (fp16),
                               arm4_selected_states [k_max, hidden] (fp32),
                               arm4_positions [k_max], arm4_scores [k_max]
  <ctx>_payloads.json          spans, counts, knobs (debugging metadata)
"""

import argparse
import time
from pathlib import Path

from safetensors.torch import save_file

from probe.common import RUNS_DIR, read_json, write_json
from probe.capture.reflect_prompt import build_a_messages
from probe.inject.injector import ModelHarness

IM_END = "<|im_end|>"


def capture_one(h: ModelHarness, ctx: dict, note: str, k_max: int,
                layer_frac: float, sink_tokens: int) -> tuple[dict, dict]:
    msgs = build_a_messages(ctx["transcript"])
    prompt_text = h.render_chat(msgs, add_generation_prompt=True, enable_thinking=False)
    prompt_ids = h.encode(prompt_text)
    note_ids = h.encode(note + IM_END)
    n_suffix = h.encode(note).shape[1]
    span = h.token_span_for_substring(prompt_text, ctx["transcript"])

    payloads = h.capture_note_payloads(
        prompt_ids, note_ids, n_suffix=n_suffix, candidate_span=span,
        k_max=k_max, layer_frac=layer_frac, sink_tokens=sink_tokens)

    meta = {
        "context_id": ctx["context_id"],
        "prompt_tokens": int(prompt_ids.shape[1]),
        "note_tokens": int(n_suffix),
        "transcript_span": list(span),
        "k_max": int(payloads["selected_positions"].shape[0]),
        "layer_frac": layer_frac,
        "sink_tokens": sink_tokens,
        "selected_positions": payloads["selected_positions"].tolist(),
        "model": h.model_name,
        "realign": h.realign,
    }
    return meta, payloads


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="full")
    ap.add_argument("--device", default=None)
    ap.add_argument("--run", default="main",
                    help="capture run whose notes to reuse; payload files are "
                         "written next to them")
    ap.add_argument("--contexts", default="data/contexts")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--k-max", type=int, default=128,
                    help="positions stored for arm 4 (arms subset to k at use time)")
    ap.add_argument("--layer-frac", type=float, default=0.5,
                    help="rank with layers in [frac*L, L) — mid-to-late")
    ap.add_argument("--sink-tokens", type=int, default=4)
    ap.add_argument("--realign", action="store_true",
                    help="apply the LatentMAS realignment matrix when "
                         "norm-matching the payload states (default off, "
                         "matching the main run)")
    ap.add_argument("--skip-per-layer", action="store_true",
                    help="don't store the per-layer suffix states (saves "
                         "~45MB/ctx; they only matter for a future level (ii))")
    args = ap.parse_args()

    cap_dir = RUNS_DIR / args.run / "capture"
    # eager attention: capture_note_payloads needs explicit scores
    h = ModelHarness(args.model, device=args.device, realign=args.realign,
                     attn_implementation="eager")

    ctx_files = sorted(Path(args.contexts).glob("ctx_*.json"))
    if args.limit:
        ctx_files = ctx_files[: args.limit]

    for i, path in enumerate(ctx_files):
        ctx = read_json(path)
        cid = ctx["context_id"]
        out_st = cap_dir / f"{cid}_payloads.safetensors"
        if out_st.exists():
            print(f"[{i + 1}/{len(ctx_files)}] {cid}: payloads exist, skipping")
            continue
        note_path = cap_dir / f"{cid}.json"
        if not note_path.exists():
            print(f"[{i + 1}/{len(ctx_files)}] {cid}: no capture record, skipping")
            continue
        note = read_json(note_path)["note"]
        t0 = time.time()
        meta, payloads = capture_one(h, ctx, note, args.k_max,
                                     args.layer_frac, args.sink_tokens)
        tensors = {
            "arm3_suffix_states": payloads["suffix_states"].contiguous(),
            "arm4_selected_states": payloads["selected_states"].contiguous(),
            "arm4_positions": payloads["selected_positions"].contiguous(),
            "arm4_scores": payloads["selected_scores"].contiguous(),
        }
        if not args.skip_per_layer:
            tensors["arm3_suffix_per_layer"] = payloads["suffix_per_layer"].contiguous()
        save_file(tensors, str(out_st))
        write_json(meta, cap_dir / f"{cid}_payloads.json")
        print(f"[{i + 1}/{len(ctx_files)}] {cid}: suffix {meta['note_tokens']} tok, "
              f"selected {meta['k_max']} of span {meta['transcript_span']}, "
              f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
