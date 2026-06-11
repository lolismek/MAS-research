"""Unit tests for level-(i) embedding injection.

Run:  python -m probe.inject.test_inject [--model tiny] [--device mps]

Covers the Phase-0 gates from PROBE_PLAN.md:
- round-trip: re-injecting a span's own input embeddings at the same
  position is a no-op (logit deltas ~ numerics)
- positional correctness: injecting at a shifted position is NOT a no-op
- mask correctness: nothing attends *from* earlier positions to slots
  (causality), and slots ARE attendable (changing them moves final logits)
- latent rolling: shapes, finiteness, norm matching, and a generation
  smoke test with injected rolled latents
"""

import argparse

import torch

from probe.inject.injector import ModelHarness

PROMPT = (
    "You are picking up a colleague's debugging session. Their note says the "
    "slowdown comes from the tokenizer cache, parameter beta=0.42 must not "
    "change, and the retry logic in fetch.py was never tested. Write a plan."
)


def report(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="tiny")
    ap.add_argument("--device", default=None)
    ap.add_argument("--dtype", default=None)
    args = ap.parse_args()

    h = ModelHarness(args.model, device=args.device, dtype=args.dtype)
    print(f"model={h.model_name} device={h.device} dtype={h.dtype} "
          f"hidden={h.hidden_size} target_norm={h.target_norm:.3f}")

    msgs = [{"role": "user", "content": PROMPT}]
    ids = h.encode(h.render_chat(msgs))
    T = ids.shape[1]
    # tolerance: fp32 forward noise; bf16 needs a looser bound
    tol = 1e-3 if h.dtype == torch.float32 else 5e-2
    results = []

    # 1. ids vs own-embeds forward — identical logits
    l_ids = h.logits(ids=ids)
    l_emb = h.logits(embeds=h.embed(ids))
    d = (l_ids - l_emb).abs().max().item()
    results.append(report("embed round-trip (ids vs inputs_embeds)", d < tol, f"max|Δlogit|={d:.2e}"))

    # 2. split-and-concat injection of the span's own embeddings — no-op
    a, b = T // 3, 2 * T // 3
    pre, span, post = ids[:, :a], ids[:, a:b], ids[:, b:]
    inj = h.build_injected_embeds(pre, h.embed(span).squeeze(0), post)
    l_inj = h.logits(embeds=inj)
    d = (l_ids - l_inj).abs().max().item()
    results.append(report("own-state re-injection is a no-op", d < tol, f"max|Δlogit|={d:.2e}"))

    # 3. positional correctness: injecting the span one slot later must change logits
    shifted = torch.cat(
        [h.embed(pre), h.embed(post[:, :1]), h.embed(span).to(h.dtype),
         h.embed(post[:, 1:])], dim=1)
    d_shift = (h.logits(embeds=shifted)[0, -1] - l_ids[0, -1]).abs().max().item()
    results.append(report("shifted injection changes final logits", d_shift > 10 * tol,
                          f"max|Δlogit|={d_shift:.2e}"))

    # 4. causality: random slots must not affect logits BEFORE the slot
    m = 8
    rand_latents = torch.randn(m, h.hidden_size) * (h.target_norm / h.hidden_size ** 0.5)
    inj_rand = h.build_injected_embeds(pre, rand_latents, post)
    l_rand = h.logits(embeds=inj_rand)
    d_before = (l_rand[0, : a - 1] - l_ids[0, : a - 1]).abs().max().item()
    results.append(report("slots invisible to earlier positions (causal mask)",
                          d_before < tol, f"max|Δlogit| before slot={d_before:.2e}"))

    # 5. slots are attendable: different slot contents → different final logits
    inj_rand2 = h.build_injected_embeds(pre, -rand_latents, post)
    d_slots = (h.logits(embeds=inj_rand2)[0, -1] - l_rand[0, -1]).abs().max().item()
    results.append(report("slot contents influence downstream logits", d_slots > 10 * tol,
                          f"max|Δlogit|={d_slots:.2e}"))

    # 6. latent rolling: shape, finiteness, norm match
    lat = h.roll_latents(ids, m)
    norms = lat.float().norm(dim=-1)
    ok = (
        lat.shape == (m, h.hidden_size)
        and torch.isfinite(lat).all().item()
        and (norms - h.target_norm).abs().max().item() < 0.01 * h.target_norm
    )
    results.append(report("latent rolling shapes/norms", ok,
                          f"shape={tuple(lat.shape)} norm range=[{norms.min():.2f},{norms.max():.2f}]"))

    # 7. generation with injected rolled latents stays well-formed text
    text = h.generate_from_embeds(h.build_injected_embeds(pre, lat, post),
                                  max_new_tokens=60, seed=0)
    ok = len(text) > 20 and any(c.isalpha() for c in text)
    results.append(report("generation with injected latents is text", ok, repr(text[:80])))

    print(f"\n{sum(results)}/{len(results)} passed")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
