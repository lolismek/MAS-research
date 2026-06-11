"""Level-(i) embedding-space injection, adapted from LatentMAS (Gen-Verse/LatentMAS).

Two mechanisms:

1. Latent rolling (writer side, arm 2): after a forward pass over agent A's
   context, the last-layer last-token hidden state is norm-matched to the
   input-embedding scale and fed back as ``inputs_embeds`` for m steps
   ("rolled latent thoughts"). The m vectors are the payload.

2. Embedding injection (reader side): agent B's prompt is tokenized in two
   halves around an injection point; the payload vectors are concatenated
   between the halves' input embeddings and generation runs from
   ``inputs_embeds``. The model computes K/V for the slots itself, so RoPE
   and GQA need no special handling (LatentMAS's validated level-(i) path).

3. Note-turn payload capture (writer side, arms 3/4): re-forward A's pass in
   two stages — prompt with ``use_cache``, then the note tokens against that
   cache with ``output_attentions`` + ``output_hidden_states`` (requires an
   eager-attention harness). Yields the note tokens' last-layer states (arm 3,
   the note "as A computed it") and a SnapKV-style attention ranking of
   context positions (arm 4: sink-masked, mid-to-late layers, max over heads,
   mean over note queries), whose last-layer states form the selected payload.

4. Level-(ii) cache-space injection (reader side, arms 3kv/3ikv): instead of
   re-encoding writer states from B's layer 1, splice A's K/V for the payload
   tokens directly into B's cache at every layer. K/V at layer l are
   deterministic functions of the hidden state ENTERING layer l
   (input_layernorm → W_k/W_v → per-head k-norm → RoPE), so the per-layer
   states ``capture_note_payloads`` stores suffice — K/V are reconstructed
   with RoPE applied at B's slot positions, avoiding the positional mismatch
   of shipping A's rotated keys verbatim.

Norm matching follows LatentMAS ``_apply_latent_realignment``. With
``realign=False`` (their CLI default, used for the 2026-06-11 main run):
identity map + rescale to the mean input-embedding row norm. With
``realign=True``: first apply their ridge least-squares map W from the
output-embedding (unembedding) space to the input-embedding space, fit over
vocab rows — W = (Wo^T Wo + 1e-5 I)^{-1} Wo^T Wi — then rescale. For models
with untied embeddings (Qwen3-8B) W is a non-trivial correction; for tied
models (0.6B/4B) it is ~identity.
"""

from typing import Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from probe.common import resolve_device, resolve_dtype, resolve_model


class ModelHarness:
    def __init__(
        self,
        model_name: str,
        device: str | None = None,
        dtype: str | None = None,
        attn_implementation: str | None = None,
        realign: bool = False,
    ):
        self.model_name = resolve_model(model_name)
        self.device = resolve_device(device)
        self.dtype = resolve_dtype(self.device, dtype)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, use_fast=True)
        kwargs = {}
        if attn_implementation:
            kwargs["attn_implementation"] = attn_implementation
        self.model = (
            AutoModelForCausalLM.from_pretrained(self.model_name, dtype=self.dtype, **kwargs)
            .to(self.device)
            .eval()
        )
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        emb = self.model.get_input_embeddings().weight
        self.hidden_size = emb.shape[1]
        # LatentMAS normalization target: mean L2 norm of input-embedding rows.
        self.target_norm = emb.detach().to(torch.float32).norm(dim=1).mean().item()
        self.realign = realign
        self.realign_matrix = self._compute_realign_matrix() if realign else None

    # ---------- text plumbing ----------

    def render_chat(self, messages, add_generation_prompt: bool = True,
                    enable_thinking: bool = False) -> str:
        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=add_generation_prompt,
            enable_thinking=enable_thinking,
        )

    def encode(self, text: str) -> torch.Tensor:
        return self.tokenizer(
            text, return_tensors="pt", add_special_tokens=False
        )["input_ids"].to(self.device)

    def decode(self, ids: torch.Tensor) -> str:
        return self.tokenizer.decode(ids, skip_special_tokens=True)

    def embed(self, ids: torch.Tensor) -> torch.Tensor:
        return self.model.get_input_embeddings()(ids)

    # ---------- generation ----------

    @torch.no_grad()
    def generate_from_ids(
        self,
        ids: torch.Tensor,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
        seed: Optional[int] = None,
        greedy: bool = False,
    ) -> str:
        if seed is not None:
            torch.manual_seed(seed)
        out = self.model.generate(
            input_ids=ids,
            attention_mask=torch.ones_like(ids),
            max_new_tokens=max_new_tokens,
            do_sample=not greedy,
            temperature=temperature if not greedy else None,
            top_p=top_p if not greedy else None,
            pad_token_id=self.tokenizer.pad_token_id,
        )
        return self.decode(out[0, ids.shape[1]:]).strip()

    @torch.no_grad()
    def generate_from_embeds(
        self,
        embeds: torch.Tensor,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
        seed: Optional[int] = None,
        greedy: bool = False,
    ) -> str:
        if seed is not None:
            torch.manual_seed(seed)
        mask = torch.ones(embeds.shape[:2], dtype=torch.long, device=self.device)
        out = self.model.generate(
            inputs_embeds=embeds,
            attention_mask=mask,
            max_new_tokens=max_new_tokens,
            do_sample=not greedy,
            temperature=temperature if not greedy else None,
            top_p=top_p if not greedy else None,
            pad_token_id=self.tokenizer.pad_token_id,
        )
        # With inputs_embeds, generate returns only the new tokens.
        return self.decode(out[0]).strip()

    def build_injected_embeds(
        self,
        pre_ids: torch.Tensor,
        latents: Optional[torch.Tensor],
        post_ids: torch.Tensor,
    ) -> torch.Tensor:
        """[embed(pre) | latents | embed(post)] along the sequence axis.

        latents: [m, hidden] (or None for a no-payload control).
        """
        parts = [self.embed(pre_ids)]
        if latents is not None and latents.numel() > 0:
            parts.append(latents.to(self.device, self.dtype).unsqueeze(0))
        parts.append(self.embed(post_ids))
        return torch.cat(parts, dim=1)

    # ---------- latent rolling (writer side) ----------

    @torch.no_grad()
    def _compute_realign_matrix(self) -> torch.Tensor:
        """LatentMAS latent-space realignment matrix (their formula verbatim):
        ridge least-squares map from unembedding space to input-embedding
        space, fit over vocab rows. [hidden, hidden], float32, on device."""
        w_in = self.model.get_input_embeddings().weight.detach()
        w_out = self.model.get_output_embeddings().weight.detach()
        # linalg.solve is unsupported on MPS; the matmuls are fine on CPU too
        dev = self.device if str(self.device).startswith("cuda") else "cpu"
        w_in = w_in.to(dev, torch.float32)
        w_out = w_out.to(dev, torch.float32)
        gram = w_out.T @ w_out
        gram += 1e-5 * torch.eye(gram.shape[0], device=dev)
        rhs = w_out.T @ w_in
        return torch.linalg.solve(gram, rhs).to(self.device)

    def _norm_match(self, hidden: torch.Tensor) -> torch.Tensor:
        h = hidden.to(torch.float32)
        if self.realign_matrix is not None:
            h = h @ self.realign_matrix
        scale = self.target_norm / h.norm(dim=-1, keepdim=True).clamp_min(1e-6)
        return (h * scale).to(self.dtype)

    @torch.no_grad()
    def roll_latents(self, ids: torch.Tensor, m: int) -> torch.Tensor:
        """Forward over ids, then roll m latent steps. Returns [m, hidden]:
        the norm-matched vectors actually fed back as inputs_embeds (these are
        what the reader injects)."""
        out = self.model(
            input_ids=ids,
            attention_mask=torch.ones_like(ids),
            use_cache=True,
            output_hidden_states=True,
            return_dict=True,
        )
        past = out.past_key_values
        last_hidden = out.hidden_states[-1][:, -1, :]
        vecs = []
        for _ in range(m):
            latent = self._norm_match(last_hidden)
            vecs.append(latent.squeeze(0).detach().clone())
            past_len = past.get_seq_length()
            mask = torch.ones((1, past_len + 1), dtype=torch.long, device=self.device)
            out = self.model(
                inputs_embeds=latent.unsqueeze(1),
                attention_mask=mask,
                past_key_values=past,
                use_cache=True,
                output_hidden_states=True,
                return_dict=True,
            )
            past = out.past_key_values
            last_hidden = out.hidden_states[-1][:, -1, :]
        return torch.stack(vecs, dim=0)

    # ---------- level-(ii) cache-space injection (arms 3kv / 3ikv) ----------

    @staticmethod
    def cache_layer_kv(cache, layer_idx: int):
        """One layer's (keys, values) across transformers cache APIs."""
        if hasattr(cache, "layers"):
            return cache.layers[layer_idx].keys, cache.layers[layer_idx].values
        return cache.key_cache[layer_idx], cache.value_cache[layer_idx]

    @torch.no_grad()
    def build_kv_injected_cache(
        self, pre_ids: torch.Tensor, per_layer_states: torch.Tensor
    ) -> tuple:
        """Forward pre_ids with use_cache, then append S rows per layer
        reconstructed from another pass's per-layer hidden states, RoPE'd at
        the slot positions [P, P+S). Returns (cache, S).

        per_layer_states: [n_layers(+1), S, hidden]; row l is the hidden
        state ENTERING decoder layer l (transformers' output_hidden_states
        convention); a trailing final-output row, if present, is ignored.
        """
        from transformers.models.qwen3.modeling_qwen3 import apply_rotary_pos_emb

        out = self.model(
            input_ids=pre_ids,
            attention_mask=torch.ones_like(pre_ids),
            use_cache=True,
            return_dict=True,
        )
        cache = out.past_key_values
        decoder = self.model.model
        if per_layer_states.shape[0] < len(decoder.layers):
            raise ValueError(
                f"need ≥{len(decoder.layers)} per-layer state rows, "
                f"got {per_layer_states.shape[0]}")
        S = per_layer_states.shape[1]
        P = pre_ids.shape[1]
        pos = torch.arange(P, P + S, device=self.device).unsqueeze(0)
        ref = torch.empty((1, S, 1), dtype=self.dtype, device=self.device)
        cos, sin = decoder.rotary_emb(ref, pos)
        for idx, layer in enumerate(decoder.layers):
            h = per_layer_states[idx].to(self.device, self.dtype).unsqueeze(0)
            hs = layer.input_layernorm(h)
            attn = layer.self_attn
            hd = attn.head_dim
            k = attn.k_norm(attn.k_proj(hs).view(1, S, -1, hd)).transpose(1, 2)
            v = attn.v_proj(hs).view(1, S, -1, hd).transpose(1, 2)
            k, _ = apply_rotary_pos_emb(k, k, cos, sin)
            cache.update(k, v, idx)
        return cache, S

    @torch.no_grad()
    def generate_with_kv_injection(
        self,
        pre_ids: torch.Tensor,
        per_layer_states: torch.Tensor,
        post_ids: torch.Tensor,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
        seed: Optional[int] = None,
        greedy: bool = False,
    ) -> str:
        """Generate with the payload injected in CACHE space at the slot
        positions. Slot positions are filled with pad ids in input_ids purely
        for length accounting — the prefilled cache covers them, so generate's
        first step forwards only the post tokens and the pad ids are never
        embedded."""
        cache, S = self.build_kv_injected_cache(pre_ids, per_layer_states)
        pad = torch.full((1, S), self.tokenizer.pad_token_id,
                         dtype=torch.long, device=self.device)
        full_ids = torch.cat([pre_ids, pad, post_ids], dim=1)
        if seed is not None:
            torch.manual_seed(seed)
        out = self.model.generate(
            input_ids=full_ids,
            attention_mask=torch.ones_like(full_ids),
            past_key_values=cache,
            max_new_tokens=max_new_tokens,
            do_sample=not greedy,
            temperature=temperature if not greedy else None,
            top_p=top_p if not greedy else None,
            pad_token_id=self.tokenizer.pad_token_id,
        )
        return self.decode(out[0, full_ids.shape[1]:]).strip()

    # ---------- note-turn payload capture (arms 3 / 4) ----------

    def token_span_for_substring(self, text: str, sub: str) -> tuple[int, int]:
        """Token [start, end) of a substring within text, under the same
        no-special-tokens encoding ``encode`` uses. Used to restrict arm-4
        selection to the transcript span of A's prompt."""
        start_char = text.index(sub)
        end_char = start_char + len(sub)
        enc = self.tokenizer(text, add_special_tokens=False,
                             return_offsets_mapping=True)
        toks = [i for i, (s, e) in enumerate(enc["offset_mapping"])
                if e > start_char and s < end_char]
        if not toks:
            raise ValueError("substring maps to no tokens")
        return toks[0], toks[-1] + 1

    @torch.no_grad()
    def capture_note_payloads(
        self,
        prompt_ids: torch.Tensor,
        note_ids: torch.Tensor,
        n_suffix: int | None = None,
        candidate_span: tuple[int, int] | None = None,
        k_max: int = 128,
        layer_frac: float = 0.5,
        sink_tokens: int = 4,
    ) -> dict:
        """Arm-3 and arm-4 payloads from one re-forward of A's note turn.

        prompt_ids: A's full prompt (context + reflect instruction + gen prompt).
        note_ids:   the note tokens as generated (may include the trailing
                    <|im_end|>); all of them serve as ranking queries.
        n_suffix:   how many leading note tokens to keep states for (arm 3);
                    default all of note_ids.
        candidate_span: token [start, end) within prompt_ids that arm-4
                    selection may pick from (the transcript span); default all.
        Returns dict of CPU tensors:
          suffix_states   [n_suffix, hidden]  norm-matched (ready to inject)
          suffix_per_layer [n_layers+1, n_suffix, hidden]  raw, for level (ii)
          selected_states [k, hidden]  norm-matched, score-descending order
          selected_positions [k]  prompt token positions, same order
          selected_scores [k]
        """
        out_a = self.model(
            input_ids=prompt_ids,
            attention_mask=torch.ones_like(prompt_ids),
            use_cache=True,
            output_hidden_states=True,
            return_dict=True,
        )
        ctx_states = out_a.hidden_states[-1][0]  # [T_prompt, hidden], last layer
        t0 = prompt_ids.shape[1]
        mask = torch.ones((1, t0 + note_ids.shape[1]), dtype=torch.long,
                          device=self.device)
        out_b = self.model(
            input_ids=note_ids,
            attention_mask=mask,
            past_key_values=out_a.past_key_values,
            use_cache=True,
            output_attentions=True,
            output_hidden_states=True,
            return_dict=True,
        )
        if not out_b.attentions or out_b.attentions[0] is None:
            raise RuntimeError(
                "attention scores unavailable — load the harness with "
                "attn_implementation='eager' for payload capture")

        n_suffix = n_suffix or note_ids.shape[1]
        suffix_states = self._norm_match(out_b.hidden_states[-1][0, :n_suffix])
        suffix_per_layer = torch.stack(
            [hs[0, :n_suffix] for hs in out_b.hidden_states], dim=0)

        # SnapKV-style ranking of prompt positions by the attention the note
        # tokens place on them: mid-to-late layers, mean over note queries,
        # max over heads, mean over layers.
        n_layers = len(out_b.attentions)
        first_layer = int(n_layers * layer_frac)
        scores = torch.zeros(t0, dtype=torch.float32, device=self.device)
        for att in out_b.attentions[first_layer:]:  # [1, H, n_note, T]
            scores += att[0, :, :, :t0].float().mean(dim=1).max(dim=0).values
        scores /= n_layers - first_layer

        lo, hi = candidate_span or (0, t0)
        allowed = torch.zeros(t0, dtype=torch.bool, device=self.device)
        allowed[max(lo, sink_tokens):hi] = True
        scores = scores.masked_fill(~allowed, float("-inf"))
        k = min(k_max, int(allowed.sum().item()))
        top_scores, top_pos = scores.topk(k)

        return {
            "suffix_states": suffix_states.float().cpu(),
            "suffix_per_layer": suffix_per_layer.to(torch.float16).cpu(),
            "selected_states": self._norm_match(ctx_states[top_pos]).float().cpu(),
            "selected_positions": top_pos.cpu(),
            "selected_scores": top_scores.float().cpu(),
        }

    # ---------- scoring (tests + coherence metric) ----------

    @torch.no_grad()
    def logits(self, ids: Optional[torch.Tensor] = None,
               embeds: Optional[torch.Tensor] = None) -> torch.Tensor:
        assert (ids is None) != (embeds is None)
        if ids is not None:
            out = self.model(input_ids=ids, attention_mask=torch.ones_like(ids))
        else:
            mask = torch.ones(embeds.shape[:2], dtype=torch.long, device=self.device)
            out = self.model(inputs_embeds=embeds, attention_mask=mask)
        return out.logits

    @torch.no_grad()
    def continuation_nll(self, prefix_embeds: torch.Tensor,
                         continuation_ids: torch.Tensor) -> float:
        """Mean per-token NLL of a fixed continuation under a (possibly
        injected) prefix. Used for the coherence/perplexity check."""
        full = torch.cat([prefix_embeds, self.embed(continuation_ids)], dim=1)
        logits = self.logits(embeds=full)
        p = prefix_embeds.shape[1]
        t = continuation_ids.shape[1]
        pred = logits[0, p - 1 : p + t - 1, :].float()
        nll = torch.nn.functional.cross_entropy(pred, continuation_ids[0])
        return nll.item()

    @torch.no_grad()
    def attention_to_slots(
        self,
        embeds: torch.Tensor,
        slot_start: int,
        slot_len: int,
        query_start: int,
    ) -> dict:
        """Attention mass that positions >= query_start place on the injected
        slots, per layer (averaged over heads and query positions). Requires a
        harness loaded with attn_implementation='eager'."""
        mask = torch.ones(embeds.shape[:2], dtype=torch.long, device=self.device)
        out = self.model(
            inputs_embeds=embeds, attention_mask=mask,
            output_attentions=True, return_dict=True,
        )
        per_layer = []
        for att in out.attentions:  # [1, heads, T, T]
            a = att[0, :, query_start:, :].float()
            slot_mass = a[:, :, slot_start : slot_start + slot_len].sum(-1).mean().item()
            per_layer.append(slot_mass)
        return {
            "per_layer": per_layer,
            "mean": sum(per_layer) / len(per_layer),
            "max": max(per_layer),
            "uniform_baseline": slot_len / embeds.shape[1],
        }
