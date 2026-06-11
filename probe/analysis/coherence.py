"""Phase-2 coherence battery (model-bound — run on the GPU box).

Run:  python -m probe.analysis.coherence --model full --run main --n 10

Gates from PROBE_PLAN.md before spending on the full run:
1. Perplexity: NLL of B's arm-1 (text-only) continuation evaluated under the
   arm-2 injected prefix must not blow up vs the arm-1 prefix (ΔNLL ~ small).
2. Attention diagnostic: attention mass B's continuation tokens place on the
   injected slots. ~Zero mass predicts arm 2 ≡ arm 1 and is itself the key
   negative finding. Computed with an eager-attention model instance — only
   here, never for generation (FlashAttention/SDPA can't return scores).
3. Side-by-side dump of generations for manual eyeballing.

Requires capture + at least arm-1/arm-2 outputs for the first --n contexts.
"""

import argparse
from pathlib import Path

import torch
from safetensors.torch import load_file

from probe.common import RUNS_DIR, read_json, write_json
from probe.arms.b_prompts import LATENT_SENTINEL, build_b_messages
from probe.inject.injector import ModelHarness


def b_prefix_parts(h: ModelHarness, ctx: dict, note: str):
    text = h.render_chat(build_b_messages(ctx, note),
                         add_generation_prompt=True, enable_thinking=False)
    pre_text, post_text = text.split(LATENT_SENTINEL)
    return h.encode(pre_text), h.encode(post_text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="full")
    ap.add_argument("--device", default=None)
    ap.add_argument("--run", default="main")
    ap.add_argument("--contexts", default="data/contexts")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--skip-attention", action="store_true",
                    help="skip the eager-attention diagnostic (memory-heavy)")
    args = ap.parse_args()

    run_dir = RUNS_DIR / args.run
    out_dir = run_dir / "analysis"
    h = ModelHarness(args.model, device=args.device)

    ctx_files = sorted(Path(args.contexts).glob("ctx_*.json"))[: args.n]
    rows, side_by_side = [], ["# Side-by-side B generations (s0)\n"]

    for path in ctx_files:
        ctx = read_json(path)
        cid = ctx["context_id"]
        cap_path = run_dir / "capture" / f"{cid}.json"
        arm1_path = run_dir / "arms" / f"{cid}_arm1_s0.json"
        if not (cap_path.exists() and arm1_path.exists()):
            print(f"{cid}: missing capture/arm outputs, skipping")
            continue
        note = read_json(cap_path)["note"]
        latents = load_file(str(run_dir / "capture" / f"{cid}.safetensors"))["arm2_latents"]
        cont_text = read_json(arm1_path)["text"]
        cont_ids = h.encode(cont_text)

        pre_ids, post_ids = b_prefix_parts(h, ctx, note)
        prefix_arm1 = h.build_injected_embeds(pre_ids, None, post_ids)
        prefix_arm2 = h.build_injected_embeds(pre_ids, latents, post_ids)
        nll1 = h.continuation_nll(prefix_arm1, cont_ids)
        nll2 = h.continuation_nll(prefix_arm2, cont_ids)
        rows.append({"context_id": cid, "nll_arm1_prefix": nll1,
                     "nll_arm2_prefix": nll2, "delta_nll": nll2 - nll1,
                     "slot_start": int(pre_ids.shape[1]),
                     "slot_len": int(latents.shape[0])})
        print(f"{cid}: NLL arm1 {nll1:.3f} → arm2 {nll2:.3f} (Δ {nll2 - nll1:+.3f})")

        side_by_side.append(f"\n## {cid}\n")
        for arm in ("1", "2", "5"):
            p = run_dir / "arms" / f"{cid}_arm{arm}_s0.json"
            if p.exists():
                side_by_side.append(f"**arm {arm}**\n\n```\n{read_json(p)['text'][:700]}\n```\n")

    result = {"perplexity_check": rows}
    if rows:
        mean_d = sum(r["delta_nll"] for r in rows) / len(rows)
        result["mean_delta_nll"] = mean_d
        print(f"\nmean ΔNLL (arm2 prefix vs arm1 prefix): {mean_d:+.4f}")

    if not args.skip_attention and rows:
        print("\nattention diagnostic (eager attention instance)...")
        h_eager = ModelHarness(args.model, device=args.device,
                               attn_implementation="eager")
        att_rows = []
        for r, path in zip(rows, ctx_files):
            ctx = read_json(path)
            cid = ctx["context_id"]
            note = read_json(run_dir / "capture" / f"{cid}.json")["note"]
            latents = load_file(str(run_dir / "capture" / f"{cid}.safetensors"))["arm2_latents"]
            cont_ids = h_eager.encode(read_json(run_dir / "arms" / f"{cid}_arm2_s0.json")["text"])
            pre_ids, post_ids = b_prefix_parts(h_eager, ctx, note)
            prefix = h_eager.build_injected_embeds(pre_ids, latents, post_ids)
            full = torch.cat([prefix, h_eager.embed(cont_ids)], dim=1)
            diag = h_eager.attention_to_slots(
                full, slot_start=r["slot_start"], slot_len=r["slot_len"],
                query_start=prefix.shape[1])
            att_rows.append({"context_id": cid, **{k: diag[k] for k in ("mean", "max", "uniform_baseline")}})
            print(f"{cid}: slot attention mean={diag['mean']:.5f} max-layer={diag['max']:.5f} "
                  f"(uniform baseline {diag['uniform_baseline']:.5f})")
        result["attention_diagnostic"] = att_rows

    write_json(result, out_dir / "coherence.json")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "side_by_side.md").write_text("\n".join(side_by_side))
    print(f"\nwrote {out_dir}/coherence.json and side_by_side.md")


if __name__ == "__main__":
    main()
