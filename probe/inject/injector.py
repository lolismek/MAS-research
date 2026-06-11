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
