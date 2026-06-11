"""Phase-3 B-side runner for arms 1, 2, 5.

Run:  python -m probe.arms.run_arms --model full --run main --arms 1,2,5 --samples 3

Arms (PROBE_PLAN.md):
  1  text-only baseline: the note alone
  2  rolled latent thoughts: note + m latent vectors injected as inputs_embeds
     at the sentinel position (visible text identical to arm 1)
  5  raw-context ceiling: note + full session log as plain text
  5t optional truncated variant of 5 (last --truncate-tokens tokens of the log)

Every arm runs through the same embeds-based generation path (arm 1 simply
injects nothing), so arms differ only in payload. Sampling is paired: sample
s uses seed (base_seed + s) in every arm.

Outputs: runs/<run>/arms/<ctx>_arm<arm>_s<s>.json
"""

import argparse
import time
from pathlib import Path

import torch
from safetensors.torch import load_file

from probe.common import RUNS_DIR, read_json, write_json
from probe.arms.b_prompts import LATENT_SENTINEL, build_b_messages
from probe.inject.injector import ModelHarness


def truncate_to_last_tokens(h: ModelHarness, text: str, n_tokens: int) -> str:
    ids = h.encode(text)
    if ids.shape[1] <= n_tokens:
        return text
    return h.decode(ids[0, -n_tokens:])


def run_one(h: ModelHarness, ctx: dict, note: str, arm: str,
            latents: torch.Tensor | None, seed: int,
            max_new_tokens: int, temperature: float,
            truncate_tokens: int) -> dict:
    raw = None
    if arm == "5":
        raw = ctx["transcript"]
    elif arm == "5t":
        raw = truncate_to_last_tokens(h, ctx["transcript"], truncate_tokens)

    msgs = build_b_messages(ctx, note, raw_transcript=raw)
    text = h.render_chat(msgs, add_generation_prompt=True, enable_thinking=False)
    pre_text, post_text = text.split(LATENT_SENTINEL)
    pre_ids, post_ids = h.encode(pre_text), h.encode(post_text)

    inj = latents if arm == "2" else None
    embeds = h.build_injected_embeds(pre_ids, inj, post_ids)
    out = h.generate_from_embeds(embeds, max_new_tokens=max_new_tokens,
                                 temperature=temperature, seed=seed)

    payload_tokens = {"1": 0, "2": 0 if inj is None else inj.shape[0]}.get(arm)
    if payload_tokens is None:  # 5 / 5t: transcript tokens added on top of arm 1
        payload_tokens = h.encode(raw).shape[1]
    return {
        "context_id": ctx["context_id"],
        "arm": arm,
        "seed": seed,
        "text": out,
        "prompt_tokens": int(embeds.shape[1]),
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

    arms = args.arms.split(",")
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
        latents = None
        if "2" in arms:
            latents = load_file(str(cap_dir / f"{cid}.safetensors"))["arm2_latents"]
        t0 = time.time()
        for arm in arms:
            for s in range(args.samples):
                out_path = out_dir / f"{cid}_arm{arm}_s{s}.json"
                if out_path.exists():
                    continue
                rec = run_one(h, ctx, note, arm, latents, args.base_seed + s,
                              args.max_new_tokens, args.temperature,
                              args.truncate_tokens)
                write_json(rec, out_path)
        print(f"[{i + 1}/{len(ctx_files)}] {cid}: arms {args.arms} × {args.samples} "
              f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
