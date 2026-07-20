# Latent handoff arms — implementation log

Running log for the L-KV / L-THOUGHT / L-PROBE build (LITREVIEW.md "Recommended
package", L-STEER skipped). Handoff doc for the orchestrating session.

## 2026-07-20 — recon findings (before any code)

**GPU availability (tigerfish):** A100-SXM4-**40GB** x4 (not 80G). GPUs 2,3 =
vLLM serving the text arms (untouched). GPU 0 has a running job by user
`horvitz` (16.3G, 69% util) → per ground rules we avoid it. **Only GPU 1 is
free** → we run ONE latent server (port 8802), not the two instances the task
sketch suggested. If GPU 0 frees up later, a second instance on 8803 is a
one-line launch.

**Architecture surprise (affects L-KV design):** the AWQ checkpoint
(`/tmp/aij2115/models/qwen36-awq`, name_or_path tclf90/Qwen3.6-35B-A3B-AWQ) is
`model_type: qwen3_5_moe`, `Qwen3_5MoeForConditionalGeneration` — a **hybrid
linear-attention MoE**, NOT a plain GQA+RoPE transformer:
- 40 layers, `layer_types` = 3x `linear_attention` (GatedDeltaNet) : 1x
  `full_attention`, `full_attention_interval: 4` → **only 10 layers (idx 3,7,
  ...,39) have positional KV at all**.
- full-attention: GQA num_kv_heads=2, num_heads=16, head_dim=256,
  `partial_rotary_factor` 0.25, mrope_interleaved (text-only ⇒ standard
  positions), rope_theta 1e7.
- linear_attention layers carry a **fixed-size recurrent state**
  (conv_states + recurrent_states per layer), not per-position KV. "Selecting
  n KV positions" is only meaningful for the 10 full-attention layers.
- MoE: 256 experts, 8 active; AWQ quantizes ONLY the expert MLPs
  (`modules_to_not_convert` = self_attn, linear_attn, shared_expert, gate,
  layer 0, visual, mtp) — attention weights are fp16, good for us.
- Multimodal wrapper (vision tower in checkpoint); we use it text-only.

**Design consequence for L-KV** (deviation from the LITREVIEW sketch, forced
by the architecture): the "KV of the last n positions" artifact =
- last-n K/V slices of the **10 full-attention layers** (slot ledger: n
  positions; bit ledger: n × 10 layers × 2 (K,V) × 2 kv_heads × 256 dims × 2
  bytes = n × 20 KB);
- linear-attention layers start EMPTY for B (fresh recurrent state built from
  B's own tokens). This keeps the artifact position-bounded (the honest analog
  of "n tokens of memory").
- optional extra arm `lkv_state`: additionally hand the linear layers'
  recurrent+conv states (a fixed-size summary of A's ENTIRE context — capacity
  ledger must declare it as full-context, not n-bounded). Implemented as a
  flag; reported as its own point, not part of the n-sweep.

**Positions/RoPE plan:** re-prefill A's transcript under HF (deterministic),
slice keys WITH their baked-in rotations at original absolute positions
T-n..T, and give B's tokens position_ids/cache_position starting at T. Since
RoPE is relative, B sees correct distances to the prefix; B's internal
distances are unchanged. This works for non-contiguous selections too (keys
keep their original positional identity), so attention-scored selection needs
no re-rotation either.

**HF stack:** transformers 5.14.1 + torch 2.11.0+cu128 in /tmp/aij2115/vllmenv
knows `qwen3_5_moe` natively. Cache = transformers 5.x `DynamicCache
(config=...)` with per-layer `.layers[i]` objects: `keys/values` for
full-attention, `conv_states/recurrent_states` for deltanet → we can build a
cache with populated full-attn layers and empty linear layers.
No `autoawq` in the venv — first open question is whether HF loads the AWQ
expert weights (vLLM uses its own AWQ-MoE path). Fallback if not: documented
blocker + try `--no-deps` autoawq or dequantize experts to fp16 on load
(won't fit 40G? experts dominate ⇒ likely blocker if AWQ load fails).

**Serving/proxy chain for B-side latent episodes** (reuses the calibrated
text path): harness on piranha → SECOND proxy instance (:8745, same
proxy_server.py, TINKER_BASE=http://localhost:8802/v1) → ssh tunnel :8802 →
latent server on tigerfish GPU 1. The latent server exposes an OpenAI-style
/v1/chat/completions that applies the Qwen chat template itself (thinking
left ON, matching vLLM; the proxy strips <think> and parses XML tool calls,
same as text arms). The handoff artifact reference travels IN-BAND as a
`[[LATENT:<arm>:<artifact_id>]]` marker inside the system prompt (survives the
proxy untouched); the server strips it and injects the latent prefix.

**L-PROBE data plan:** pilot repos = {flask, sphinx, scrapy, black, requests,
seaborn, pylint, gym, sympy} (30 instances). Disjoint-by-repo training pool =
the other 12 repos in syncbench_300_callee: fastapi 4, pytest 8, spacy 10,
pillow 11, pycaret 11, matplotlib 4, transformers 4, optuna 3, flaml 4,
mlflow 3, whisper 2, scikit-learn 1 → 65 candidates. Need phase-1 k=12 waves
on piranha for these (udocker image availability to be checked).

## Status
- [x] recon
- [ ] HF load + parity check vs vLLM
- [ ] server.py (prefill_capture / make_artifact / generate)
- [ ] KV injection coherence
- [ ] latent thoughts coherence
- [ ] piranha proxy :8745 + tunnel :8802
- [ ] arms/build_artifacts integration (lkv, lkv_notekv, lkv_rand, lthought, lthought_rand, lprobe, lprobe_shuffled)
- [ ] end-to-end single-instance smokes
- [ ] L-PROBE capture + training wave + probes
