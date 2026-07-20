"""Custom HF loader for the Qwen3.6-35B-A3B AWQ checkpoint.

Why this exists: the QuantTrio/tclf90 AWQ checkpoint stores the MoE experts
vLLM-style — per-expert `experts.{i}.{gate,up,down}_proj.{qweight,qzeros,
scales}` (AWQ GEMM int4) — while HF's `Qwen3_5MoeExperts` wants FUSED fp16 3D
parameters (`gate_up_proj` [E,2I,H]); and transformers' AWQ integration only
converts nn.Linear modules, so stock `from_pretrained` cannot load it (fails
in replace_with_awq_linear before weight loading even starts; see
IMPLEMENTATION_LOG.md 2026-07-20).

Approach:
- instantiate `Qwen3_5MoeForCausalLM` (text-only; drops the vision tower and
  the mtp head, which `_keys_to_ignore_on_load_unexpected` documents as
  optional) on the meta device, fp16;
- swap `mlp.experts` of layers 1..39 for `AWQExperts`, which keeps the packed
  int4 buffers stacked per expert and DEQUANTIZES HIT EXPERTS ON THE FLY in
  the forward (pure-torch AWQ GEMM unpack — no autoawq/gptqmodel kernels);
  layer 0 is unquantized in the checkpoint and keeps the stock fused module;
- stream the safetensors shards ourselves, remapping
  `model.language_model.*` -> `model.*` and packing expert tensors.

Everything else (attention, deltanet, shared expert, router, embeddings,
lm_head) is fp16 in the checkpoint with names that match the HF module tree
exactly. Total GPU footprint ~23 GB on one A100-40G.
"""
import glob
import os
import re
import time

import torch
import torch.nn as nn
from accelerate import init_empty_weights
from safetensors import safe_open
from transformers import AutoConfig
from transformers.activations import ACT2FN
from transformers.models.qwen3_5_moe.modeling_qwen3_5_moe import (
    Qwen3_5MoeForCausalLM,
)

AWQ_REVERSE_ORDER = [0, 4, 1, 5, 2, 6, 3, 7]
GROUP = 128
BITS = 4


def _unpack_int4(x):
    """[..., n, m] int32 -> [..., n, m*8] ints in 0..15 with AWQ column order
    reversed (AutoAWQ's unpack_awq + reverse_awq_order, batched)."""
    shifts = torch.arange(0, 32, BITS, device=x.device, dtype=torch.int32)
    v = torch.bitwise_right_shift(x.unsqueeze(-1),
                                  shifts.view(*([1] * x.dim()), -1))
    v = torch.bitwise_and(v, 0xF)
    m8 = x.shape[-1] * 8
    rev = torch.arange(m8, device=x.device).view(-1, len(AWQ_REVERSE_ORDER))
    rev = rev[:, AWQ_REVERSE_ORDER].reshape(-1)
    return v.reshape(*x.shape[:-1], m8)[..., rev]


def dequant_awq(qweight, qzeros, scales):
    """AWQ GEMM tensors -> fp16 weight [..., in, out] (use as y = x @ w)."""
    w = _unpack_int4(qweight).to(torch.float16)
    z = _unpack_int4(qzeros).to(torch.float16).repeat_interleave(GROUP, dim=-2)
    s = scales.repeat_interleave(GROUP, dim=-2)
    return (w - z) * s


class AWQExperts(nn.Module):
    """Drop-in for Qwen3_5MoeExperts holding per-expert AWQ-packed weights.

    Buffers ({p}=gate|up|down): {p}_qweight [E,in,out/8] int32,
    {p}_qzeros [E,in/128,out/8] int32, {p}_scales [E,in/128,out] fp16.
    gate/up: in=H, out=I; down: in=I, out=H.
    """

    BATCH_DEQUANT_MIN_TOKENS = 64   # prefill: dequant all experts in one shot

    def __init__(self, config):
        super().__init__()
        E = config.num_experts
        H = config.hidden_size
        I = config.moe_intermediate_size
        self.num_experts = E
        self.act_fn = ACT2FN[config.hidden_act]
        for proj, fin, fout in (("gate", H, I), ("up", H, I), ("down", I, H)):
            self.register_buffer(f"{proj}_qweight",
                                 torch.empty(E, fin, fout // 8, dtype=torch.int32))
            self.register_buffer(f"{proj}_qzeros",
                                 torch.empty(E, fin // GROUP, fout // 8,
                                             dtype=torch.int32))
            self.register_buffer(f"{proj}_scales",
                                 torch.empty(E, fin // GROUP, fout,
                                             dtype=torch.float16))

    def _w(self, proj, e=None):
        qw = getattr(self, f"{proj}_qweight")
        qz = getattr(self, f"{proj}_qzeros")
        s = getattr(self, f"{proj}_scales")
        if e is None:
            return dequant_awq(qw, qz, s)
        return dequant_awq(qw[e], qz[e], s[e])

    def forward(self, hidden_states, top_k_index, top_k_weights):
        final = torch.zeros_like(hidden_states)
        with torch.no_grad():
            expert_mask = nn.functional.one_hot(
                top_k_index, num_classes=self.num_experts).permute(2, 1, 0)
            hit = torch.greater(expert_mask.sum(dim=(-1, -2)), 0).nonzero()[:, 0]
            hit = hit[hit < self.num_experts]
        if hidden_states.shape[0] >= self.BATCH_DEQUANT_MIN_TOKENS:
            # prefill: dequantize ALL experts in three batched ops
            Wg, Wu, Wd = self._w("gate"), self._w("up"), self._w("down")
            row = {int(e): int(e) for e in hit.tolist()}
        else:
            # decode / small batches: batch-dequantize only the HIT experts
            # (the per-expert python loop with per-projection dequant was
            # kernel-launch-bound at ~2 tok/s; this path gives ~3-4x)
            Wg = dequant_awq(self.gate_qweight[hit], self.gate_qzeros[hit],
                             self.gate_scales[hit])
            Wu = dequant_awq(self.up_qweight[hit], self.up_qzeros[hit],
                             self.up_scales[hit])
            Wd = dequant_awq(self.down_qweight[hit], self.down_qzeros[hit],
                             self.down_scales[hit])
            row = {int(e): j for j, e in enumerate(hit.tolist())}
        for e in hit.tolist():
            top_k_pos, token_idx = torch.where(expert_mask[e])
            x = hidden_states[token_idx]
            j = row[e]
            cur = (self.act_fn(x @ Wg[j]) * (x @ Wu[j])) @ Wd[j]
            cur = cur * top_k_weights[token_idx, top_k_pos, None]
            final.index_add_(0, token_idx, cur.to(final.dtype))
        return final


_EXPERT_RE = re.compile(
    r"model\.layers\.(\d+)\.mlp\.experts\.(\d+)\.(gate|up|down)_proj\.(qweight|qzeros|scales|weight)$")


def load_model(model_dir, device="cuda:0", verbose=True):
    t0 = time.time()
    cfg = AutoConfig.from_pretrained(model_dir).get_text_config()
    for attr in ("quantization_config",):
        if hasattr(cfg, attr):
            delattr(cfg, attr)
    prev_dtype = torch.get_default_dtype()
    torch.set_default_dtype(torch.float16)
    try:
        with init_empty_weights():
            model = Qwen3_5MoeForCausalLM(cfg)
            for i, layer in enumerate(model.model.layers):
                if i > 0:
                    layer.mlp.experts = AWQExperts(cfg)
        model = model.to_empty(device=device)
        # buffers made garbage by to_empty: recompute rotary inv_freq
        model.model.rotary_emb = type(model.model.rotary_emb)(config=cfg).to(device)
    finally:
        torch.set_default_dtype(prev_dtype)

    tensors = dict(model.named_parameters())
    tensors.update(dict(model.named_buffers()))
    for p in tensors.values():
        p.requires_grad_(False) if p.is_leaf and p.dtype.is_floating_point else None
    filled, unexpected = set(), []
    I = cfg.moe_intermediate_size
    for shard in sorted(glob.glob(os.path.join(model_dir, "model-*.safetensors"))):
        with safe_open(shard, framework="pt", device="cpu") as f:
            for key in f.keys():
                if key.startswith("mtp") or ".visual." in key \
                        or key.startswith("model.visual"):
                    continue
                name = key.replace("model.language_model.", "model.", 1)
                m = _EXPERT_RE.match(name)
                t = f.get_tensor(key)
                if m and m.group(4) != "weight":
                    li, ei, proj, kind = (int(m.group(1)), int(m.group(2)),
                                          m.group(3), m.group(4))
                    buf = tensors[f"model.layers.{li}.mlp.experts.{proj}_{kind}"]
                    buf[ei].copy_(t.to(device=buf.device, dtype=buf.dtype))
                    filled.add(name)
                elif m and m.group(4) == "weight":
                    # layer 0's unquantized per-expert weights -> fused module
                    li, ei, proj = int(m.group(1)), int(m.group(2)), m.group(3)
                    if proj == "down":
                        dst = tensors[f"model.layers.{li}.mlp.experts.down_proj"]
                        dst[ei].copy_(t.to(device=dst.device, dtype=dst.dtype))
                    else:
                        dst = tensors[f"model.layers.{li}.mlp.experts.gate_up_proj"]
                        off = 0 if proj == "gate" else I
                        dst[ei, off:off + I].copy_(
                            t.to(device=dst.device, dtype=dst.dtype))
                    filled.add(name)
                elif name in tensors:
                    dst = tensors[name]
                    dst.data.copy_(t.to(device=dst.device, dtype=dst.dtype))
                    filled.add(name)
                else:
                    unexpected.append(name)
    missing = [n for n in tensors
               if n not in filled
               and not _EXPERT_RE.match(n)
               and ".experts." not in n
               and "rotary_emb" not in n]
    if verbose:
        print(f"[awq_moe] loaded in {time.time()-t0:.0f}s; "
              f"filled={len(filled)} unexpected={len(unexpected)} "
              f"missing={missing[:8]}", flush=True)
    if missing:
        raise RuntimeError(f"missing weights after load: {missing[:20]}")
    try:
        from transformers import GenerationConfig
        model.generation_config = GenerationConfig.from_pretrained(model_dir)
    except Exception as e:
        print(f"[awq_moe] no generation_config loaded: {e}", flush=True)
    model.eval()
    return model
