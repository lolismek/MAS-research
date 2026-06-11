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
- realignment: matrix shape/finiteness; for tied-embedding models the
  LatentMAS ridge LS solution must be ~identity (first rolled latent
  unchanged vs realign-off)
- note-turn payload capture (arms 3/4): suffix-state shapes/norms, selected
  positions confined to the candidate span (sink-masked, unique, scores
  descending), determinism across calls, generation smoke with the suffix
  payload injected (needs a second, eager-attention model instance)
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

    # 8. realignment matrix: shape/finiteness; for tied-embedding models
    # (0.6B/4B) the ridge LS solution must be ~identity, so realigned rolling
    # must reproduce the realign-off latents
    h.realign_matrix = h._compute_realign_matrix()
    W = h.realign_matrix.float()
    ok = W.shape == (h.hidden_size, h.hidden_size) and torch.isfinite(W).all().item()
    detail = f"shape={tuple(W.shape)}"
    tied = getattr(h.model.config, "tie_word_embeddings", False)
    if tied:
        d_eye = (W - torch.eye(h.hidden_size, device=W.device)).abs().max().item()
        ok = ok and d_eye < 1e-2
        detail += f" tied: max|W-I|={d_eye:.2e}"
    lat_re = h.roll_latents(ids, m)
    norms_re = lat_re.float().norm(dim=-1)
    ok = ok and torch.isfinite(lat_re).all().item() \
        and (norms_re - h.target_norm).abs().max().item() < 0.01 * h.target_norm
    if tied:
        # only the FIRST latent: later steps are autoregressive, so even a
        # ~1e-4 deviation of W from identity compounds chaotically
        d_lat = (lat_re[0] - lat[0]).float().abs().max().item()
        ok = ok and d_lat < 10 * tol
        detail += f" max|Δlatent_0|={d_lat:.2e}"
    h.realign_matrix = None
    results.append(report("realignment matrix sane (rolling norms; ~identity if tied)",
                          ok, detail))

    # 9. note-turn payload capture (arms 3/4) — needs eager attention
    h9 = ModelHarness(args.model, device=args.device, dtype=args.dtype,
                      attn_implementation="eager")
    transcript = (
        "attempt 1: greedy packing, score 0.512. attempt 2: simulated "
        "annealing with T0=2.5, score 0.541. observation: the corner "
        "heuristic only helps when N is prime; retry logic untested."
    )
    p_text = h9.render_chat([{"role": "user", "content":
                              f"Session log:\n\n{transcript}\n\nWrite a one-line note."}])
    p_ids = h9.encode(p_text)
    note = "Annealing beat greedy; T0=2.5 was load-bearing."
    n_ids = h9.encode(note + "<|im_end|>")
    n_suffix = h9.encode(note).shape[1]
    span = h9.token_span_for_substring(p_text, transcript)
    k_max = 16
    pl = h9.capture_note_payloads(p_ids, n_ids, n_suffix=n_suffix,
                                  candidate_span=span, k_max=k_max)
    pos = pl["selected_positions"]
    sc = pl["selected_scores"]
    norms_s = pl["suffix_states"].norm(dim=-1)
    norms_k = pl["selected_states"].norm(dim=-1)
    k_expect = min(k_max, span[1] - max(span[0], 4))
    ok = (
        pl["suffix_states"].shape == (n_suffix, h9.hidden_size)
        and pl["suffix_per_layer"].shape[1] == n_suffix
        and torch.isfinite(pl["suffix_states"]).all().item()
        and (norms_s - h9.target_norm).abs().max().item() < 0.01 * h9.target_norm
        and (norms_k - h9.target_norm).abs().max().item() < 0.01 * h9.target_norm
        and pos.shape[0] == k_expect
        and len(set(pos.tolist())) == pos.shape[0]
        and bool(((pos >= max(span[0], 4)) & (pos < span[1])).all().item())
        and bool((sc[:-1] >= sc[1:]).all().item())
    )
    pl2 = h9.capture_note_payloads(p_ids, n_ids, n_suffix=n_suffix,
                                   candidate_span=span, k_max=k_max)
    ok = ok and pos.tolist() == pl2["selected_positions"].tolist()
    results.append(report("payload capture (suffix shapes/norms, selection in span, deterministic)",
                          ok, f"suffix={n_suffix} tok, selected {pos.shape[0]} of span {span}"))

    # 10. generation with the injected note-suffix payload stays text
    text = h.generate_from_embeds(
        h.build_injected_embeds(pre, pl["suffix_states"], post),
        max_new_tokens=60, seed=0)
    ok = len(text) > 20 and any(c.isalpha() for c in text)
    results.append(report("generation with injected suffix states is text", ok, repr(text[:80])))

    print(f"\n{sum(results)}/{len(results)} passed")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
