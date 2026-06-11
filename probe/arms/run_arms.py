"""Phase-3 B-side runner for all arms.

Run:  python -m probe.arms.run_arms --model full --run main --arms 1,2,5 --samples 3

Arms (PROBE_PLAN.md §arms and §in-place-arms):
  alongside the note —
    1     text-only baseline: the note alone
    2     rolled latent thoughts: note + m latent vectors at the sentinel
          (visible text identical to arm 1)
    2r    as 2, latents passed through the LatentMAS realignment matrix
    3     note-suffix states: note + A's last-layer states for the note tokens
    3kv   note + A's K/V cache for the note tokens, spliced per layer into
          B's cache at the slot positions (level ii)
    4k<k> selected context states: note + top-k attention-ranked positions
          (bare "4" = k64)
    5/5t  raw-context ceiling: note + full (or truncated) session log as text
  in place of the note —
    0     no-note floor: bare scaffold, nothing injected
    2i / 2ir / 3i / 3ikv / 4ik<k>  the same payloads substituting for the
          note text (scaffold byte-identical across the in-place family)
    1e    positive control: the note's own input-embedding rows in place of
          its text — must recover ~arm-1 recall if the harness is sound

All arms except 3kv/3ikv run through the same embeds-based generation path
(the no-payload arms simply inject nothing); 3kv/3ikv inject in cache space
instead. Arms differ only in payload (and, for the in-place family, the
removed note text). Sampling is paired: sample s uses seed (base_seed + s)
in every arm.

Arms 3/4 need <ctx>_payloads.safetensors from probe.capture.capture_payloads
(3kv also needs its per-layer states); 2r needs <ctx>_realign.safetensors
from run_capture --realign --out-suffix _realign.

Outputs: runs/<run>/arms/<ctx>_arm<arm>_s<s>.json
"""

import argparse
import time
from pathlib import Path

import torch

from probe.common import RUNS_DIR, read_json, write_json
from probe.arms.b_prompts import LATENT_SENTINEL, build_b_messages
from probe.arms.payloads import load_payload, normalize_arm, parse_arm
from probe.inject.injector import ModelHarness


def truncate_to_last_tokens(h: ModelHarness, text: str, n_tokens: int) -> str:
    ids = h.encode(text)
    if ids.shape[1] <= n_tokens:
        return text
    return h.decode(ids[0, -n_tokens:])


def run_one(h: ModelHarness, ctx: dict, note: str, arm: str,
            payload: torch.Tensor | None, seed: int,
            max_new_tokens: int, temperature: float,
            truncate_tokens: int) -> dict:
    base, inplace, _ = parse_arm(arm)
    raw = None
    if base == "5":
        raw = ctx["transcript"]
    elif base == "5t":
        raw = truncate_to_last_tokens(h, ctx["transcript"], truncate_tokens)

    msgs = build_b_messages(ctx, note, raw_transcript=raw, inplace=inplace)
    text = h.render_chat(msgs, add_generation_prompt=True, enable_thinking=False)
    pre_text, post_text = text.split(LATENT_SENTINEL)
    pre_ids, post_ids = h.encode(pre_text), h.encode(post_text)

    if base == "1e":
        # control payload: the note's own input-embedding rows — exactly the
        # vectors the model reads when the note is text. Deliberately NOT
        # norm-matched: they are in-distribution by construction.
        payload = h.embed(h.encode(note)).squeeze(0)

    if base == "3kv":
        out = h.generate_with_kv_injection(
            pre_ids, payload, post_ids, max_new_tokens=max_new_tokens,
            temperature=temperature, seed=seed)
        payload_tokens = payload.shape[1]
        prompt_tokens = pre_ids.shape[1] + payload.shape[1] + post_ids.shape[1]
    else:
        embeds = h.build_injected_embeds(pre_ids, payload, post_ids)
        out = h.generate_from_embeds(embeds, max_new_tokens=max_new_tokens,
                                     temperature=temperature, seed=seed)
        prompt_tokens = embeds.shape[1]
        if base in ("5", "5t"):  # transcript tokens added on top of arm 1
            payload_tokens = h.encode(raw).shape[1]
        else:
            payload_tokens = 0 if payload is None else payload.shape[0]
    return {
        "context_id": ctx["context_id"],
        "arm": arm,
        "seed": seed,
        "text": out,
        "prompt_tokens": int(prompt_tokens),
        "payload_tokens": int(payload_tokens),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="full")
    ap.add_argument("--device", default=None)
    ap.add_argument("--run", default="main")
    ap.add_argument("--contexts", default="data/contexts")
    ap.add_argument("--arms", default="1,2,5")
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--base-seed", type=int, default=100)
    ap.add_argument("--temperature", type=float, default=0.7)
    # generous enough that all 6 answers + the plan fit; smoke run showed 450
    # truncates mid-answer, which biases against late-listed facts
    ap.add_argument("--max-new-tokens", type=int, default=700)
    ap.add_argument("--truncate-tokens", type=int, default=512)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    arms = [normalize_arm(a) for a in args.arms.split(",")]
    cap_dir = RUNS_DIR / args.run / "capture"
    out_dir = RUNS_DIR / args.run / "arms"
    h = ModelHarness(args.model, device=args.device)

    ctx_files = sorted(Path(args.contexts).glob("ctx_*.json"))
    if args.limit:
        ctx_files = ctx_files[: args.limit]

    for i, path in enumerate(ctx_files):
        ctx = read_json(path)
        cid = ctx["context_id"]
        cap_path = cap_dir / f"{cid}.json"
        if not cap_path.exists():
            print(f"[{i + 1}/{len(ctx_files)}] {cid}: no capture record, skipping")
            continue
        note = read_json(cap_path)["note"]
        t0 = time.time()
        for arm in arms:
            payload = load_payload(cap_dir, cid, arm)
            for s in range(args.samples):
                out_path = out_dir / f"{cid}_arm{arm}_s{s}.json"
                if out_path.exists():
                    continue
                rec = run_one(h, ctx, note, arm, payload, args.base_seed + s,
                              args.max_new_tokens, args.temperature,
                              args.truncate_tokens)
                write_json(rec, out_path)
        print(f"[{i + 1}/{len(ctx_files)}] {cid}: arms {','.join(arms)} × {args.samples} "
              f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
