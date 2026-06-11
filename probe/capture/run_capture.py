"""Phase-1 A-side capture: note generation + arm-2 payload + verbalized labels.

Run:  python -m probe.capture.run_capture --model tiny --run smoke --limit 3

Per context:
1. Roll agent A (the model) through the session transcript with the
   CORAL-style reflect prompt; generate the note (thinking off, sampled).
2. Re-forward [A's full prompt + note] and roll m latent steps from the final
   state (LatentMAS mechanism) — the arm-2 payload. The latents are harvested
   from the very pass that contains the note, as the plan requires.
3. Label each planted fact verbalized/unverbalized against the note text.

Outputs under runs/<run>/capture/:
  <ctx>.json              note text, labels, token counts
  <ctx>.safetensors       arm2_latents [m, hidden]
  capture_summary.json    gate stats (unverbalized fraction should be ~half)
"""

import argparse
import time

import torch
from safetensors.torch import save_file

from probe.common import RUNS_DIR, read_json, write_json
from probe.capture.reflect_prompt import build_a_messages
from probe.contexts.facts import fact_matches
from probe.inject.injector import ModelHarness


def capture_one(h: ModelHarness, ctx: dict, m: int, max_note_tokens: int, seed: int,
                note: str | None = None) -> tuple[dict, torch.Tensor]:
    msgs = build_a_messages(ctx["transcript"])
    prompt_text = h.render_chat(msgs, add_generation_prompt=True, enable_thinking=False)
    prompt_ids = h.encode(prompt_text)
    if note is None:
        note = h.generate_from_ids(prompt_ids, max_new_tokens=max_note_tokens,
                                   temperature=0.7, seed=seed)

    # arm-2 payload: roll m latents from the pass containing prompt + note
    full_ids = h.encode(prompt_text + note + "<|im_end|>")
    latents = h.roll_latents(full_ids, m)

    verbalized = {f["fact_id"]: fact_matches(f, note) for f in ctx["facts"]}
    record = {
        "context_id": ctx["context_id"],
        "note": note,
        "verbalized": verbalized,
        "n_unverbalized": sum(not v for v in verbalized.values()),
        "prompt_tokens": prompt_ids.shape[1],
        "note_tokens": h.encode(note).shape[1],
        "m": m,
        "seed": seed,
        "model": h.model_name,
        "realign": h.realign,
    }
    return record, latents


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="tiny")
    ap.add_argument("--device", default=None)
    ap.add_argument("--run", default="dev")
    ap.add_argument("--contexts", default="data/contexts")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--m", type=int, default=8)
    ap.add_argument("--max-note-tokens", type=int, default=320)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--realign", action="store_true",
                    help="apply the LatentMAS realignment matrix when rolling "
                         "latents (their --latent_space_realign; default off, "
                         "matching the main run)")
    ap.add_argument("--notes-from", default=None,
                    help="reuse the notes of an existing capture run (run name) "
                         "instead of regenerating — keeps notes byte-identical "
                         "so only the latents differ across runs")
    ap.add_argument("--out-suffix", default="",
                    help="suffix for output filenames (e.g. _realign) so a "
                         "re-capture can land in the SAME run dir without "
                         "clobbering the original latents/records")
    args = ap.parse_args()

    out_dir = RUNS_DIR / args.run / "capture"
    out_dir.mkdir(parents=True, exist_ok=True)
    h = ModelHarness(args.model, device=args.device, realign=args.realign)

    from pathlib import Path
    ctx_files = sorted(Path(args.contexts).glob("ctx_*.json"))
    if args.limit:
        ctx_files = ctx_files[: args.limit]

    summary = []
    for i, path in enumerate(ctx_files):
        ctx = read_json(path)
        st_path = out_dir / f"{ctx['context_id']}{args.out_suffix}.safetensors"
        rec_path = out_dir / f"{ctx['context_id']}{args.out_suffix}.json"
        if st_path.exists() and rec_path.exists():
            record = read_json(rec_path)
            summary.append({
                "context_id": ctx["context_id"],
                "n_unverbalized": record["n_unverbalized"],
                "note_tokens": record["note_tokens"],
            })
            print(f"[{i + 1}/{len(ctx_files)}] {ctx['context_id']}: exists, skipping")
            continue
        t0 = time.time()
        note = None
        if args.notes_from:
            src = RUNS_DIR / args.notes_from / "capture" / f"{ctx['context_id']}.json"
            note = read_json(src)["note"]
        record, latents = capture_one(h, ctx, args.m, args.max_note_tokens, args.seed,
                                      note=note)
        if args.notes_from:
            record["notes_from"] = args.notes_from
        save_file({"arm2_latents": latents.contiguous().to(torch.float32)},
                  str(st_path))
        write_json(record, rec_path)
        summary.append({
            "context_id": ctx["context_id"],
            "n_unverbalized": record["n_unverbalized"],
            "note_tokens": record["note_tokens"],
        })
        print(f"[{i + 1}/{len(ctx_files)}] {ctx['context_id']}: "
              f"{record['n_unverbalized']}/6 unverbalized, "
              f"{record['note_tokens']} note tokens, {time.time() - t0:.0f}s")

    n = len(summary)
    unv = [s["n_unverbalized"] for s in summary]
    gate = {
        "n_contexts": n,
        "mean_unverbalized": sum(unv) / n,
        "min_unverbalized": min(unv),
        "contexts_with_zero_unverbalized": sum(u == 0 for u in unv),
        "gate_note": "healthy is ~3/6 unverbalized; if ~0, shorten the note instruction or raise K",
        "model": h.model_name,
        "realign": h.realign,
        "per_context": summary,
    }
    write_json(gate, out_dir / f"capture_summary{args.out_suffix}.json")
    print(f"\nmean unverbalized: {gate['mean_unverbalized']:.2f}/6 across {n} contexts")


if __name__ == "__main__":
    main()
