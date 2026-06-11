"""Phase-2 coherence battery (model-bound — run on the GPU box).

Run:  python -m probe.analysis.coherence --model full --run main --n 10 [--arm 2]

Gates from PROBE_PLAN.md before spending on the full run, for one payload
arm (--arm: 2, 3, 4k64, 2i, 3i, 4ik64, ...):
1. Perplexity: NLL of the baseline text-only continuation evaluated under the
   payload-injected prefix must not blow up vs the baseline prefix (ΔNLL
   small). The baseline is arm 1 for alongside arms (identical visible text)
   and arm 0 for in-place arms (identical scaffold).
2. Attention diagnostic: attention mass B's continuation tokens place on the
   injected slots. ~Zero mass predicts payload ≡ baseline and is itself the
   key negative finding. Computed with an eager-attention model instance —
   only here, never for generation (FlashAttention/SDPA can't return scores).
3. Side-by-side dump of generations for manual eyeballing (all arms found).

Requires capture (+ payloads for arms 3/4) and s0 outputs of --arm and its
baseline for the first --n contexts.
"""

import argparse
from pathlib import Path

import torch

from probe.common import RUNS_DIR, read_json, write_json
from probe.arms.b_prompts import LATENT_SENTINEL, build_b_messages
from probe.arms.payloads import load_payload, normalize_arm, parse_arm
from probe.inject.injector import ModelHarness


def b_prefix_parts(h: ModelHarness, ctx: dict, note: str, inplace: bool):
    text = h.render_chat(build_b_messages(ctx, note, inplace=inplace),
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
    ap.add_argument("--arm", default="2", help="payload arm to gate")
    ap.add_argument("--skip-attention", action="store_true",
                    help="skip the eager-attention diagnostic (memory-heavy)")
    args = ap.parse_args()

    arm = normalize_arm(args.arm)
    base, inplace, _ = parse_arm(arm)
    if base in ("3kv", "1e"):
        raise SystemExit(
            f"arm {arm}: the embeds-space coherence gates don't apply — "
            "3kv/3ikv are gated by Phase-0 tests 11/12 (KV reconstruction + "
            "positive control) and 1e IS a control; eyeball side_by_side.md")
    baseline = "0" if inplace else "1"

    run_dir = RUNS_DIR / args.run
    cap_dir = run_dir / "capture"
    out_dir = run_dir / "analysis"
    h = ModelHarness(args.model, device=args.device)

    ctx_files = sorted(Path(args.contexts).glob("ctx_*.json"))[: args.n]
    rows, side_by_side = [], [f"# Side-by-side B generations (s0)\n"]

    for path in ctx_files:
        ctx = read_json(path)
        cid = ctx["context_id"]
        cap_path = cap_dir / f"{cid}.json"
        base_path = run_dir / "arms" / f"{cid}_arm{baseline}_s0.json"
        if not (cap_path.exists() and base_path.exists()):
            print(f"{cid}: missing capture/arm-{baseline} outputs, skipping")
            continue
        note = read_json(cap_path)["note"]
        payload = load_payload(cap_dir, cid, arm)
        cont_text = read_json(base_path)["text"]
        cont_ids = h.encode(cont_text)

        pre_ids, post_ids = b_prefix_parts(h, ctx, note, inplace)
        prefix_base = h.build_injected_embeds(pre_ids, None, post_ids)
        prefix_arm = h.build_injected_embeds(pre_ids, payload, post_ids)
        nll_b = h.continuation_nll(prefix_base, cont_ids)
        nll_a = h.continuation_nll(prefix_arm, cont_ids)
        rows.append({"context_id": cid, f"nll_arm{baseline}_prefix": nll_b,
                     f"nll_arm{arm}_prefix": nll_a, "delta_nll": nll_a - nll_b,
                     "slot_start": int(pre_ids.shape[1]),
                     "slot_len": int(payload.shape[0])})
        print(f"{cid}: NLL arm{baseline} {nll_b:.3f} → arm{arm} {nll_a:.3f} "
              f"(Δ {nll_a - nll_b:+.3f})")

        side_by_side.append(f"\n## {cid}\n")
        for p in sorted((run_dir / "arms").glob(f"{cid}_arm*_s0.json")):
            a = read_json(p)["arm"]
            side_by_side.append(f"**arm {a}**\n\n```\n{read_json(p)['text'][:700]}\n```\n")

    result = {"arm": arm, "baseline": baseline, "perplexity_check": rows}
    if rows:
        mean_d = sum(r["delta_nll"] for r in rows) / len(rows)
        result["mean_delta_nll"] = mean_d
        print(f"\nmean ΔNLL (arm{arm} prefix vs arm{baseline} prefix): {mean_d:+.4f}")

    if not args.skip_attention and rows:
        print("\nattention diagnostic (eager attention instance)...")
        h_eager = ModelHarness(args.model, device=args.device,
                               attn_implementation="eager")
        att_rows = []
        for r, path in zip(rows, ctx_files):
            ctx = read_json(path)
            cid = ctx["context_id"]
            arm_s0 = run_dir / "arms" / f"{cid}_arm{arm}_s0.json"
            if not arm_s0.exists():
                print(f"{cid}: no arm-{arm} s0 output, skipping attention")
                continue
            note = read_json(cap_dir / f"{cid}.json")["note"]
            payload = load_payload(cap_dir, cid, arm)
            cont_ids = h_eager.encode(read_json(arm_s0)["text"])
            pre_ids, post_ids = b_prefix_parts(h_eager, ctx, note, inplace)
            prefix = h_eager.build_injected_embeds(pre_ids, payload, post_ids)
            full = torch.cat([prefix, h_eager.embed(cont_ids)], dim=1)
            diag = h_eager.attention_to_slots(
                full, slot_start=r["slot_start"], slot_len=r["slot_len"],
                query_start=prefix.shape[1])
            att_rows.append({"context_id": cid, **{k: diag[k] for k in ("mean", "max", "uniform_baseline")}})
            print(f"{cid}: slot attention mean={diag['mean']:.5f} max-layer={diag['max']:.5f} "
                  f"(uniform baseline {diag['uniform_baseline']:.5f})")
        result["attention_diagnostic"] = att_rows

    suffix = "" if arm == "2" else f"_arm{arm}"
    write_json(result, out_dir / f"coherence{suffix}.json")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "side_by_side.md").write_text("\n".join(side_by_side))
    print(f"\nwrote {out_dir}/coherence{suffix}.json and side_by_side.md")


if __name__ == "__main__":
    main()
