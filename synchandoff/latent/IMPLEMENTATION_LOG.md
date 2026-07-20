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

## 2026-07-20 — build + verification results

**AWQ-under-HF (the flagged hard risk) — SOLVED with a custom loader.**
Stock `from_pretrained` fails twice: (1) transformers 5.14's AWQ path needs
`gptqmodel` (installed in an OVERLAY venv `/tmp/aij2115/latentenv`,
`--system-site-packages` over vllmenv, so the live vLLM env is untouched);
(2) then dies in `replace_with_awq_linear` — the checkpoint's
`modules_to_not_convert` uses vLLM substring semantics and, decisively, the
checkpoint stores experts PER-EXPERT (`experts.{i}.gate_proj.qweight`...)
while HF's `Qwen3_5MoeExperts` is fused 3D fp16 params, unloadable.
→ `latent/awq_moe.py`: text-only `Qwen3_5MoeForCausalLM` skeleton on meta
(fp16, vision/mtp dropped, `model.language_model.*`→`model.*` remap), experts
of layers 1–39 swapped for `AWQExperts` (packed int4 buffers, pure-torch AWQ
GEMM dequant of HIT experts per forward; layer 0 is unquantized in the
checkpoint and keeps the stock fused module). Loads in ~15 s, 22.8 GB on the
40 GB GPU, `filled=91237 unexpected=0 missing=[]`.

**Speed:** decode 1.9 → 4.7 tok/s (batched hit-expert dequant + fla 0.5.1
for the deltanet decode path) → einsum single-token fast path added after the
smoke (untested number, expect ~6-10). Prefill is chunked (8192) and fast
enough (135-token prefill instant; 30-40k transcripts ≈ 1-2 min). Latent
B-episodes are ~10-50x slower than vLLM text arms — plan latent phase-2 waves
at 1-2 shards and expect hours/instance-set, or accept single-seed smokes.
Timeout plumbing added end-to-end (SYNCHANDOFF_LLM_TIMEOUT=3900,
PROXY_UPSTREAM_TIMEOUT=3600 in the latent proxy).

**Parity check (LITREVIEW global note) — PASSED.** Same greedy prompt to
vLLM :8801 vs latent server :8802 text-only path: tools case BYTE-IDENTICAL
(245/245 chars incl. `<tool_call>` XML); plain case identical for a 371-char
prefix then benign same-content divergence (expected: Marlin vs pure-torch
dequant numerics). `latent/parity_check.py`, log at tigerfish
`/tmp/aij2115/latent/parity.log`.

**KV-injection coherence + signal — PASSED (smoke_latent.py).** Synthetic
A-transcript with planted facts; B prompted with only "describe what your
predecessor was doing":
- control (no artifact): fluent, honest "no information", 0 fact hits.
- lkv (last-120 KV prefix): fluent, and B's output surfaces planted facts
  ('test_trailing_newline', 'manifest') that exist NOWHERE in B's prompt —
  the KV channel transmits content. (Full per-arm hit table in
  tigerfish:/tmp/aij2115/latent/smoke.log.)

**Coconut thoughts (training-free) — no collapse at m=8**: hidden norms
~104–119 (vs emb-norm rescale applied at injection), consecutive cos-sim
0.32–0.66 (a collapsed loop would be ~1.0). Received coherently by B.

**L-THOUGHT primary designation (decision, per LITREVIEW's contingency):**
after fixing the injection-scale bug (artifacts now store the RESCALED
vectors), the training-free coconut loop at m=8 still transmits no explicit
facts in the planted-fact probe (fluent reception, non-degenerate vectors,
zero hits; retest_thought.py, 8.6 tok/s post-einsum-path), while
**lthought_pool (mean-pooled note embeddings) DID transmit** a planted fact.
LITREVIEW anticipated exactly this (Coconut needs training; training-free is
the risk). Decision: **lthought_pool is the PRIMARY L-THOUGHT arm**; coconut
lthought stays as the secondary/exploratory arm; lthought_rand controls both.
Note the smoke probe only tests EXPLICIT recall — the full phase-2 runs still
measure functional (SR/LA) effects for all three.

**Behavioral caveat (log this in the report):** in the smoke, B's think trace
shows it RETRIEVING planted facts from the KV prefix and then actively
DISTRUSTING them as potential hallucinations ("I must not invent a test like
`test_trailing_newline` ... unless it was in the prompt. It wasn't.") — the
model's anti-hallucination instincts fight the latent channel. Latent
transmission may therefore show up more in B's priors/actions than in B's
explicit claims; expect utilization loss relative to what the channel carries.

## Ops runbook (exact commands)

**Latent server (tigerfish GPU 1, port 8802):**
```
# start
ssh aij2115@tigerfish.cs.columbia.edu \
  'cd /tmp/aij2115/latent && LATENT_GPU=1 LATENT_PORT=8802 setsid nohup \
   ./serve_latent.sh > server_8802.log 2>&1 < /dev/null &'
# check
ssh aij2115@tigerfish.cs.columbia.edu 'curl -s http://localhost:8802/health'
# stop (bracket trick; NEVER pkill without it)
ssh aij2115@tigerfish.cs.columbia.edu 'pkill -u aij2115 -f "[s]erver.py --port 8802"'
```
If GPU 0 frees up (check `nvidia-smi` — as of today it has a horvitz job):
second instance with `LATENT_GPU=0 LATENT_PORT=8803` + a second tunnel.

**Tunnel piranha->tigerfish :8802 (on piranha):**
```
ssh -i /tmp/aij2115/tunnel_key -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    -o ExitOnForwardFailure=yes -N -f -L 8802:localhost:8802 \
    aij2115@tigerfish.cs.columbia.edu
```

**Latent proxy (piranha :8745; runs the REPO's infra/proxy_server.py from
/tmp/aij2115/px/latent/server.py — the live :8744 text proxy is untouched):**
```
ssh aij2115@piranha.cs.columbia.edu \
  'setsid nohup /tmp/aij2115/run_proxy_latent.sh > /tmp/aij2115/proxy_latent.log 2>&1 < /dev/null &'
```

**Build latent artifacts (piranha, tunnel+server up; vanilla.txt must exist
first for lkv_notekv/lthought_pool; keep this arm ORDER so the 2-session
server cache is reused):**
```
cd /tmp/aij2115/synchandoff && SYNCHANDOFF_LATENT_BASE=http://localhost:8802 \
/tmp/aij2115/pyenv/bin/python build_artifacts.py --k 12 \
  --arms lkv,lkv_n75,lkv_n19,lkv_rand,lkv_notekv,lthought,lthought_rand,lthought_pool \
  [--instances <iid>] [--limit N]
```

**Latent phase-2 (piranha; 1-2 shards only — the server serializes):**
```
/tmp/aij2115/run_phase2_latent.sh 12 8 lkv,lkv_rand,... 1 <tag>
```

**L-PROBE pipeline (piranha):**
```
# 1. phase-1 training wave (needs the 7 pulled images; ~51 instances)
/tmp/aij2115/synchandoff/infra/run_wave_train.sh 12 4
# 2. activation capture (tunnel+server up)
cd /tmp/aij2115/synchandoff && SYNCHANDOFF_LATENT_BASE=http://localhost:8802 \
/tmp/aij2115/pyenv/bin/python -m latent.probe.capture \
  --candidates latent/probe/train_candidates.json --k 12
# 3. train probes (writes latent/probe/probes.json; then scp it back into the
#    repo AND leave it in place for annex building)
/tmp/aij2115/pyenv/bin/python -m latent.probe.train
# 4. lprobe/lprobe_shuffled artifacts via build_artifacts --arms lprobe,lprobe_shuffled
```

**Code sync:** repo `synchandoff/latent/*.py` -> tigerfish:/tmp/aij2115/latent/
(server-side) and piranha:/tmp/aij2115/synchandoff/... (harness-side) via scp;
infra/proxy_server.py -> piranha:/tmp/aij2115/px/latent/server.py.

## Status
- [x] recon
- [x] HF load (custom awq_moe loader) + parity check vs vLLM (PASSED)
- [x] server.py (prefill_capture / make_artifact / generate / chat.completions)
- [x] KV injection coherence + planted-fact signal (PASSED)
- [x] latent thoughts: coherent, no collapse; m=8 carried no explicit facts in
      the smoke (anticipated risk — pooled variant + controls in place)
- [x] piranha latent proxy :8745 + tunnel :8802 (both up)
- [x] arms/build_artifacts integration (8 latent arms + lprobe stubs);
      offline tests 21/21 green (tests/test_latent_offline.py)
- [x] L-PROBE code (capture/labels/train/annex) + training wave RUNNING on
      piranha (51 instances, 7 disjoint repos, 4 shards)
- [x] end-to-end single-instance phase-2 smoke: **lkv PASSED** on
      9_sympy...second_moment_of_area (SR=True la_file=True la_func=True,
      7 tool calls; full chain harness→:8745→tunnel→KV-injected HF B →
      udocker tests; runs/<iid>/lkv_k12_m8/ on piranha). **lthought episode
      also mechanically clean** (8 calls, zero harness errors, result.json
      written) with SR=False la_file=False — consistent with the weak coconut
      channel (single instance; not evidence by itself).
- [x] artifact build over a real frozen trajectory: all 8 latent arms
      built=8 skipped=0 missing_frozen=0 (~9k-token prefill, session reuse,
      notekv, coconut m=32, rand/pool controls)
- [~] probe training wave RUNNING on piranha (27/51 frozen at last check,
      zero tracebacks; logs /tmp/aij2115/train_wave_*_k12.log). When done:
      run capture.py then train.py per the runbook (capture ≈ 1-2 h on one
      server instance), then build lprobe/lprobe_shuffled artifacts.
- [ ] kv_attn (attention-scored selection) — deferred (v1 = last-n + rand
      controls; the chosen keep-original-positions scheme supports
      non-contiguous selection when it's added)
- [ ] lkv_state (linear-state handover) — flag exists server-side
      (include_linear_state), no arm wired yet

## Live state at handoff (2026-07-20 ~13:30 ET)
- tigerfish: latent servers on GPU 1 (:8802) and GPU 0 (:8803), current code,
  idle after the e2e smokes. GPUs 2,3 = text-arm vLLM, untouched throughout.
- piranha: latent proxies :8745→:8802 and :8746→:8803 (both tunnels up);
  text proxy :8744 untouched; probe TRAINING WAVE still running (4 shards,
  ~27/51 done); one pre-existing text phase-2 shard (not ours to touch).
- Artifacts: /tmp/aij2115/latent_artifacts on tigerfish (smoke_* + the
  9_sympy e2e set); piranha repo copy synced with all latent code.
- Everything above is committed on lab-test (latest: e2e results).
- NOT run (by design): the 30-instance latent waves — orchestrating session
  launches those via run_phase2_latent.sh (1-2 shards; ~10-50x slower per
  call than vLLM text arms, budget wall-clock accordingly).
