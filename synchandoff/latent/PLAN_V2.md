# Latent arms — v2 plan (2026-07-20)

Full restart of the latent arms after design review. The v1 (hybrid-35B) run is
archived: cluster state at piranha:/tmp/aij2115/synchandoff_35b_archive, repo
results under results/35b_hybrid/ (classic table + all raw result.json). v1
code (latent/server.py, awq_moe.py, probe/) stays in-tree as reference;
IMPLEMENTATION_LOG.md documents what was verified there (parity, KV-injection
planted-fact signal, e2e lkv episode SR=True).

## Locked decisions

1. **Model: Qwen/Qwen3-8B, bf16, stock HF.** Dense, standard full-attention +
   RoPE on every layer (36 layers, GQA 8 KV heads) — no hybrid layers, no AWQ,
   no custom loader. Rationale: v1's Qwen3.6-35B-A3B is a hybrid (only 10/40
   layers carry KV) which weakens/complicates every latent arm, and AWQ-under-HF
   decode was ~8.6 tok/s. 8B bf16 (~16 GB) fits one A100-40G with headroom and
   decodes fast. Fallback if phase-1 sanity fails (see §Sanity): Qwen3-14B.
2. **Everything re-runs on the new model** — phase-1 (k=12), brackets, all 7
   classic arms, latent arms — so text-vs-latent comparisons are same-model.
   The 35B tables remain as a separate capability reference; never mix rows.
3. **Speed-first**: vLLM for every text-side call (phase-1 A, classic arms,
   B-side of text-output arms, summarizers); HF only where injection/capture is
   required; high parallelism everywhere; A-unsolved slice first in phase 2.

## Arms (v2 designs)

### L-KV v2 — KV handoff with smarter selection
- Primary `lkv_attn`: attention-scored position selection (KVComm-style):
  score A's positions by accumulated attention mass from the tail of A's
  context (and/or a briefing query), keep top-n, n = W. The v1
  keep-original-positions scheme already supports non-contiguous selection.
- Controls: `lkv_last` (v1 last-n), `lkv_rand` (random-n), `lkv_notekv`
  (prefill the vanilla note, hand ITS KV — channel control).
- Dense model → every layer has KV. Bit ledger: n × 36 layers × 2 × 8 heads ×
  head_dim × 2 bytes. Report slot + bit ledgers in artifact aux as before.

### L-THOUGHT v2 — aligned latent thoughts (fixes v1's distribution mismatch)
v1 finding: raw hidden-state recycling (Coconut, training-free) = fluent but
zero fact transmission; the failure is embedding/hidden distribution mismatch.
- Primary `lthought_soft`: Soft-Thinking-style soft tokens — at each latent
  step take the next-token DISTRIBUTION and feed back the probability-weighted
  mixture of INPUT-EMBEDDING vectors (stays on the embedding manifold by
  construction), with a cold-stop: end the rollout when the distribution
  entropy drops below threshold (thought has settled), cap m=32.
- Secondary `lthought_align`: LatentMAS-style alignment — map last hidden
  state through lm_head→softmax→embedding-table expectation (or an explicit
  least-squares alignment matrix fit offline) before re-injection.
- Controls: `lthought_rand` (matched-norm random vectors), `lthought_pool`
  (mean-pooled note embeddings — content-matched, mechanism-latent).

### L-PROBE v2 — belief-STRENGTH probe (full redesign per user direction)
The v1 content-probes ("which file does A believe is buggy") are dropped.
- **Probe**: ONE task-agnostic probe answering, at position t: "does the model
  currently hold a STRONG belief about what is happening?" Logistic regression
  on residual-stream activations (sweep a few middle layers, pick by val).
- **Training data (simple, synthetic, model-generated, cheap)**: matched pairs
  of short agentic-style snippets — tool outputs/observations after which the
  situation is DETERMINATE (evidence seen, conclusion follows) vs
  INDETERMINATE (ambiguous, contradictory, or missing evidence). Positions
  after the evidence get label 1/0. Include convinced-but-wrong cases so the
  probe tracks conviction, not truth. Several snippet families (debugging,
  navigation, QA, code-reading); validate on held-out families. Sanity: report
  correlation with next-token entropy (do NOT train on it). No SyncBench data
  in probe training → no leak by construction.
- **Use on a trace**: score every position of A's frozen k=12 trace →
  belief-strength curve → peak-pick (non-max suppression, min separation)
  top-P peaks → extract ±150-token windows around peaks → one vLLM call:
  "these are the moments the agent held strong beliefs; summarize what it
  believed" → W-budget note = the `lprobe` artifact.
- **Controls**: `lprobe_randsel` (same number of windows at random positions →
  same summarizer; isolates the probe's SELECTION value), `lprobe_shuffled`
  (shuffled probe weights end-to-end).
- B-side of all lprobe arms runs on vLLM (text artifacts).

## Infrastructure
- tigerfish GPU 0: vLLM serve Qwen/Qwen3-8B (thinking disabled via template,
  hermes tool parser, --served-model-name Qwen/Qwen3-8B), new port 8804.
- tigerfish GPU 1: HF latent server (adapt latent/server.py; drop awq_moe —
  stock from_pretrained bf16; keep endpoints prefill_capture / make_artifact /
  generate / chat.completions), port 8802.
- GPUs 2,3: the 35B stack stays up ONLY until the 8B stack passes smoke; then
  shut it down (our own processes only: vLLM workers + piranha proxy :8744 +
  tunnel 8801) and optionally start a second HF worker on a freed GPU.
- piranha: fresh /tmp/aij2115/synchandoff (rsync from repo). udocker container
  store + fixpacks are model-independent — reuse as-is. Tunnels + proxies per
  infra/README.md patterns (proxy :8744-style for 8804, latent proxy for 8802).
- Cost: $0 API (self-hosted); token log separate from Tinker-priced log.

## Sanity gates (cheap, do not skip)
- After phase-1 on the 30 pilot instances: check G3 numbers (A-solved rate,
  touched-repo rate) vs 35B (53%/77%). 8B will land lower; acceptable band for
  proceeding: solved 15–60%, touched ≥50%. Below → try k=16 once or fall back
  to Qwen3-14B. The A-solved/A-unsolved split adapts automatically.
- HF-vs-vLLM parity check (greedy, one tools + one plain case) before any wave.
- KV planted-fact test + soft-token planted-fact test before waves.
- Probe: val accuracy on held-out snippet families ≥0.75 before using; report
  the number regardless.

## Speed targets (aggressive but realistic)
- 8B download + both servers up: ~30 min. Phase-1 (30 inst, 10 lanes, vLLM):
  ~30-40 min. Classic artifacts (per-arm parallel): ~15 min. Classic waves
  (brackets+7 arms, 20 lanes): ~40 min. Probe data-gen + capture + train:
  ~45 min (parallel with classic waves). Latent artifacts: ~20 min. Latent
  waves: A-unsolved first; 8B HF decode should make episodes ~1-2 min.
- Order: servers → phase-1 → [classic chain] ∥ [probe chain] → latent chain.
  Chain every stage immediately; check every few minutes; no idle gaps.

## Reporting
- results/8b/: classic_k12_m8.txt, latent_k12_m8.txt, capacity ledgers,
  probe_val.txt. Final combined table = arms × {SR, LA_file, LA_func,
  mean_calls} split A-solved/A-unsolved, brackets included, 35B reference
  table kept separate.
