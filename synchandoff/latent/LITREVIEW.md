# Latent handoff arms — literature review

*Compiled 2026-07-20 (subagent web review; arXiv IDs verified as noted). Grounds the
latent-arm designs for SyncHandoff (PLAN.md §4.2 phase-2). Verification legend:
**[verified]** = arXiv record fetched/confirmed; **[listing-only]** = seen as
title+ID in search listings only.*

---

## Thread 1 — Latent / non-text inter-agent communication

### 1.1 CIPHER — "Let Models Speak Ciphers: Multiagent Debate through Embeddings" (arXiv 2310.06272, ICLR 2024) [verified]
- **What is transferred:** No sampling. At each generation step, the sender emits the *expectation of token embeddings under the output distribution* (probability-weighted average over the vocabulary embedding matrix) instead of one sampled token. The "message" is a sequence of continuous vectors in embedding space, one per step.
- **Injection:** The receiver consumes these vectors directly as input embeddings (bypassing the tokenizer/embedding lookup).
- **Gains:** +0.5 to +5.0% over natural-language debate across GSM8K, Arithmetic, and three MMLU subsets, on open-source LLaMA-family models.
- **Requirements:** Sender and receiver must share the embedding matrix in practice — i.e., same model family/tokenizer. Training-free.
- **Implementation:** Very simple: softmax probs @ embedding matrix, feed via `inputs_embeds`. The closest existing thing to a "drop-in" latent channel.

### 1.2 Coconut — "Training LLMs to Reason in a Continuous Latent Space" (arXiv 2412.06769, Meta) [verified]
- Not inter-agent, but the mechanistic template for "latent thoughts": the model's **last-layer hidden state** at step t is fed back as the **input embedding** at step t+1 ("continuous thought"), alternating language/latent modes. Requires **training** (curriculum replacing CoT steps with latent steps); training-free Coconut degrades. Code: facebookresearch/coconut. Relevance: LatentMAS (below) makes this loop training-free in the multi-agent setting.

### 1.3 "Communicating Activations Between Language Model Agents" (arXiv 2501.14082, Ramesh & Li, ICML 2025) [verified]
- **What is transferred:** an intermediate-layer activation from sender A.
- **Injection:** pause receiver B's forward pass at a chosen layer, combine B's activation with A's via a merge function f (sum/replace/learned), resume the forward pass.
- **Gains:** up to **+27%** over natural-language communication at **<1/4 the compute**, on coordination games and reasoning benchmarks; zero extra parameters in the simplest variants.
- **Requirements:** same hidden dimension; works best same-model. Practical note: this is a *per-forward-pass* intervention (hook-based), so it composes awkwardly with long agentic generations, but is trivial in HF via forward hooks.

### 1.4 State Delta Trajectory / SDE (arXiv 2506.19209, EMNLP 2025) [verified]
- Transfers text **plus** the token-wise *state transition trajectory* (deltas of hidden states across generation), arguing state *changes* carry the reasoning signal better than raw state values. SOTA among communication protocols on complex-reasoning tasks. Relevant as an "augment text with latents" middle ground rather than replacing text.

### 1.5 Cache-to-Cache / C2C (arXiv 2510.03215, ICLR 2026) [verified]
- **What is transferred:** the sender's **KV-cache**, projected and **fused into the receiver's KV-cache** by a trained neural "fuser" with a learnable per-layer gate.
- **Gains:** +6.4–14.2% over individual models; **+3.1–5.4% over text communication**; ~2× latency speedup.
- **Requirements:** the fuser is **trained** per model pair; handles *different* models (that's its point). Code: thu-nics/C2C.
- For our same-model setting, C2C is over-engineered — its value is the evidence that KV carries semantics text loses, and the gating result (not all layers benefit).

### 1.6 KVComm (arXiv 2510.03346) [verified] — and a name collision
- **Selective** KV sharing: chooses which **layers'** KV pairs to transmit via attention-importance scores with a Gaussian prior over depth; supports non-contiguous layer selection. Matches the "merge inputs into one model" upper bound while cutting compute 2.5–6× and transmission up to 3× vs full-KV transfer. Training-free scoring; same-model.
- **Caution:** there is a *different* paper called **KVCOMM** — "Online Cross-context KV-cache Communication for Efficient LLM-based Multi-agent Systems" (arXiv 2510.12872, [listing-only]) — about reusing/offset-realigning KV across differing prefix contexts in MAS. Don't conflate citations.

### 1.7 Interlat — "Enabling Agents to Communicate Entirely in Latent Space" (arXiv 2511.09149, ACL 2026) [verified]
- Transmits the temporally aligned **last-layer hidden states of the generated message** as the message itself; fine-tunes models to consume them. Beats fine-tuned CoT prompting and single-agent baselines, works even **across heterogeneous models**, and a compression variant gives up to 24× faster inference. Requires training (unlike LatentMAS).

### 1.8 LatentMAS — "Latent Collaboration in Multi-Agent Systems" (arXiv 2511.20639, ICML 2026 Spotlight) [verified]
- **The closest paper to our latent arms.** Training-free, end-to-end latent MAS: each agent (i) generates **auto-regressive latent thoughts** via last-layer hidden embeddings (Coconut-style loop, no training), and (ii) shares a **latent working memory realized as layer-wise KV caches** that transfers its internal representations to the next agent, claimed lossless.
- **Gains:** up to **+14.6% accuracy** vs text MAS, **70.8–83.7% fewer output tokens**, **4–4.3× faster** end-to-end.
- **Requirements:** same open-weights model across agents (our setting exactly). Code and data open-sourced per the abstract.
- The paper's theory section argues latent working memory has higher expressiveness per slot than text — directly relevant to the capacity-accounting problem.

### 1.9 "Dropping the D in CoT" — **could not verify**
No paper with this or a near-variant title found on arXiv or via web search. Nearest verified items in the "latent reasoning transfer" space: Coconut (§1.2), "Soft Tokens, Hard Truths" (arXiv 2509.19170) [listing-only], SpiralThinker (arXiv 2511.08983) [listing-only]. Do not cite "Dropping the D".

### 1.10 Capacity/compression side-literature (for the W-accounting)
- **Gist tokens** (arXiv 2304.08467, Mu, Li & Goodman, NeurIPS 2023) [verified]: attention-mask-trained prompt compression into k cached "gist" tokens; up to 26× compression, minimal quality loss. Establishes the "k latent slots ≈ compressed prompt" framing and that latent slots hold multiples of a text token's content.
- 2026 follow-ons seen in listings (relevant, unopened): **QKVShare** — quantized KV handoff for on-device MAS (arXiv 2605.03884) [listing-only]; **"When Less Latent Leads to Better Relay"** — information-preserving compression for latent MAS relay (arXiv 2604.13349) [listing-only]; **"Beyond Tokens"** — unified framework for latent MAS communication (arXiv 2606.05711) [listing-only].

---

## Thread 2 — Probes for belief states / ToM

### 2.1 "Language Models Represent Beliefs of Self and Others" (arXiv 2402.18496, Zhu, Zhang & Wang, ICML 2024) [verified, details fetched]
- **Setup:** Mistral-7B-Instruct on BigToM false-belief stories; probes on **attention-head activations at the final token position**, per (layer, head).
- **Probes:** logistic regression (binary) and multinomial LR (joint protagonist × oracle belief).
- **Findings:** oracle ("God's-eye") belief is decodable from many heads; **protagonist belief** decodable **>80% val accuracy** but only from a specific group of **middle-layer** heads — models preferentially encode the omniscient view.
- **Intervention works:** steering top-K heads along probe directions (α × std) — the "+TpFo" direction (protagonist-true, oracle-false) **dramatically improves false-belief task performance** with a small true-belief cost. Strongest existing evidence that belief directions are causally usable.

### 2.2 "Brittle Minds, Fixable Activations" (arXiv 2406.17513, Bortoletto et al., EMNLP 2025 Findings) [verified]
- Systematic belief-probing across model scales, base vs instruction-tuned, with **control tasks** to rule out spurious probes. Belief representations are structured and improve with **scale and fine-tuning**, but are **brittle to prompt variations**; targeted activation edits can *correct* wrong ToM inferences. Methodological checklist for our probe arm (control tasks, prompt-robustness checks).

### 2.3 "Language Models Use Lookbacks to Track Beliefs" (arXiv 2505.14685) [verified ID via listing + title match]
- Mechanistic account (Llama-3-70B family): belief tracking implemented via "lookback" attention mechanisms binding characters to observed states. Explains *where* belief info sits (attention-mediated, character-token-anchored) — motivates probing at entity mention positions, not just final token.

### 2.4 Belief-state geometry — Shai et al., "Transformers represent belief state geometry in their residual stream" (arXiv 2405.15943, NeurIPS 2024) [verified]
- On HMM-generated data, the **residual stream linearly encodes the full Bayesian belief-state simplex** (even fractal geometries), sometimes spread across layers; belief states contain information about the entire future, beyond next-token. Theoretical grounding for "the agent's residual stream contains its epistemic state about the repo". Follow-on: "Finding Belief Geometries with Sparse Autoencoders" (arXiv 2604.02685) [listing-only].

### 2.5 Gurnee & Tegmark, "Language Models Represent Space and Time" (arXiv 2310.02207, ICLR 2024) [verified]
- Template for the probe methodology everyone copies: **linear/ridge regression probes on residual stream activations** (Llama-2 family, entity last-token positions, features typically peak in early-middle-to-middle layers), robust to prompt variation. Use as the probe-engineering reference (probe residual stream at a canonical position; sweep layers; regularized linear probe).

---

## Thread 3 — Probes for deception / agent internal-state monitoring

### 3.1 Azaria & Mitchell, "The Internal State of an LLM Knows When It's Lying" (arXiv 2304.13734, EMNLP 2023 Findings) [verified]
- Feed-forward classifier on hidden-layer activations while the model reads/generates statements; **71–83% accuracy** true/false classification depending on base model. The original "truthfulness probe."

### 3.2 Representation Engineering (arXiv 2310.01405, Zou et al.) [verified]
- Contrast-pair method for extracting honesty/deception (and other concept) **directions** from population activations; both reading (probing) and control (steering). The standard recipe Apollo's probes build on. Code: andyzoujm/representation-engineering.

### 3.3 Apollo Research, "Detecting Strategic Deception Using Linear Probes" (arXiv 2502.03407, Goldowsky-Dill et al., ICML 2025) [verified]
- Linear probes on Llama-3.3-70B-Instruct activations, trained on generic honest/deceptive contrast data, tested on *realistic* agentic deception (insider trading concealment, sandbagging). **AUROC 0.96–0.999**; at 1% FPR catches **95–99%** of deceptive responses; authors still judge this insufficient as a robust defense. Code: ApolloResearch/deception-detection. Follow-up benchmark: "Benchmarking Deception Probes via Black-to-White Performance Boosts" (arXiv 2507.12691) [listing-only].

### 3.4 Anthropic, "Simple probes can catch sleeper agents" (blog post, 2024 — no arXiv) [verified as blog]
- "Defection probes": linear classifiers on residual-stream activations, trained on **generic contrast pairs** with no knowledge of the trigger, get **AUROC >99%** predicting sleeper-agent defection; directions generalize across sleeper variants of the same base model. Key claim: deception-relevant state is **linearly represented with high salience**.

### 3.5 Multi-agent-specific (2026, directly on topic)
- **"Detecting Multi-Agent Collusion Through Multi-Agent Interpretability"** (arXiv 2604.01151, Rose et al.) [verified via abstract]: extends deception probes to **group-level collusion**; NARCBench benchmark; five aggregation schemes over per-agent probe scores; models incl. **Qwen3-32B**; 1.00 AUROC in-distribution, 0.73–0.93 zero-shot transfer, 0.99–1.00 on steganographic blackjack. First real "probes for multi-agent misalignment" paper.
- **"When Latent Agents Lie: KV-Cache Integrity in Multi-Agent LLM Collaboration"** (arXiv 2606.28958, Brito & Baquero) [verified via abstract]: threat model where an agent's shared KV-cache is corrupted while its visible text stays plausible; latent collaboration beats text on Qwen3-4B (EM/F1 0.338/0.486 vs 0.231/0.369) but magnitude-check defenses are evadable; proposes HMAC manifests. Directly relevant caveat: **a KV handoff channel is unmonitorable by text-level judges.**
- **LCGuard** (arXiv 2605.22786, Asif et al.) [verified via abstract]: KV caches shared between agents leak contextual inputs and reasoning state; adversarially trained transformation preserves task semantics while minimizing reconstructability. Evidence that **raw KV is extremely information-rich** — which is exactly the capacity-accounting problem.

---

## Ranked shortlist: latent arms for SyncHandoff

Setting recap: A and B are the same open Qwen3 checkpoint on one GPU node; text arms hand over ≤ W tokens. All designs are same-model, which removes every cross-model alignment problem the literature spends most of its effort on (C2C fusers, Interlat training).

**Global implementation note:** vLLM does not expose an API for injecting arbitrary `past_key_values` or `inputs_embeds` into a request. All latent arms below should run agent B's episode under **plain HF transformers** (`past_key_values` + `DynamicCache`/`StaticCache`, `inputs_embeds`, forward hooks). To avoid a serving-stack confound, run the *text arms'* B-side under the same HF path too (or at least verify text-arm parity HF-vs-vLLM once). A's exploration phase can stay on vLLM for all arms except those needing A's activations (L-KV needs A's KV, L-PROBE needs A's hidden states — for those, either run A under HF too, or re-prefill A's transcript under HF post-hoc, which is exact for KV since prefill is deterministic given the token sequence).

### Rank 1 — Arm L-KV: bounded KV-prefix handoff ("latent working memory")
- **Transferred:** the KV cache of a *selected subset of positions* from A's final context — e.g., the last n positions, or top-n positions scored by attention importance (KVComm-style), n = W to match the text budget slot-for-slot.
- **Injection:** B is initialized with system prompt KV + A's selected KV as a prefix (positions re-indexed contiguously; with RoPE, keys must be re-rotated to the new positions or the block kept contiguous — re-prefilling A's transcript under HF and slicing the cache sidesteps most of this).
- **Capacity accounting:** two ledgers, both reported. (i) *Slot ledger:* n KV positions vs W text tokens — the "same number of attention slots B can look back at." (ii) *Bit ledger:* n × L layers × 2 × n_kv_heads × d_head × bytes — honest admission that a KV slot ≫ a text token in bits (LCGuard/2606.28958 show raw KV is rich enough to reconstruct inputs). Sweep n below W (n = W/4, W/16) to draw a latent capacity–performance curve against the text arms' W-sweep.
- **Main confound & control:** KV of *arbitrary exploration transcript* vs *curated note* mixes channel with content policy. Control arm: take the **plain-note text arm's note, prefill it, and hand its KV** — mechanically identical channel, text-limited content (should ≈ the text arm; any gap measures injection artifacts). Second control: random-position KV of the same n.
- **Effort:** low-medium (days): `past_key_values` slicing + position bookkeeping in HF. Highest risk item: Qwen3 GQA/RoPE cache layout details.
- **Support:** LatentMAS [2511.20639] (same-model, training-free KV working memory, +14.6%), KVComm [2510.03346] (selective layers/positions works), C2C [2510.03215] (KV beats text), 2606.28958 (Qwen3-4B latent > text on relay-style task).

### Rank 2 — Arm L-THOUGHT: m auto-regressive latent thoughts
- **Transferred:** A, at handoff time, is prompted to "summarize for your successor," but instead of decoding, run m steps of the Coconut loop training-free (last-layer hidden state → next input embedding, LatentMAS-style; a cheaper variant is CIPHER's expected-embedding message). The m vectors are the artifact.
- **Injection:** appended to B's prompt via `inputs_embeds` (embedding-space injection, so no KV plumbing).
- **Capacity accounting:** clean — m latent slots vs W text tokens, same input-position currency; each slot is one d_model vector (bit ledger: m × d_model × bytes, far smaller than L-KV's). The most defensible "latent W" of the three.
- **Main confound & control:** training-free latent thoughts may be off-distribution noise the receiver ignores (Coconut needed training; LatentMAS claims training-free works — verify on Qwen3 early). Controls: (a) random vectors of matched norm, (b) mean-pooled embeddings of the text note (content-matched, mechanism-latent), (c) inert arm mirroring the board_inert pattern.
- **Effort:** medium (~1 week): custom generation loop + `inputs_embeds` prefix; smoke-test heavily. LatentMAS's open-source code is the reference implementation.
- **Support:** LatentMAS [2511.20639], Coconut [2412.06769], CIPHER [2310.06272], Interlat [2511.09149] (works across models but needs training — evidence of headroom, not a recipe).

### Rank 3 — Arm L-PROBE: probe-decoded epistemic annex (probes as the handoff scientist)
- **Transferred:** text, still within W — but part of the budget is an **annex auto-generated from linear probes on A's hidden states**: e.g., per-candidate-file "A believes buggy" logits, a calibrated "fix located?" confidence, "test understood?" — probed at canonical positions (end of each A turn, residual stream, middle layers per 2402.18496/2310.02207), trained with logistic regression on held-out repos with control tasks per Bortoletto [2406.17513].
- **Why it's coherent as an arm:** it is the latent-aware sibling of the confidence-annotated and belief-ledger text arms — it asks whether A's *internal* belief state contains handoff-relevant information that A's *written* note omits (the capability-vs-structural question this project already cares about). Also doubles as a **misalignment monitor**: a probe on B reading the artifact ("did B inherit a false belief?") connects to Apollo [2502.03407]/NARCBench [2604.01151]-style monitoring of knowledge-transmission failure.
- **Capacity accounting:** trivially fair — output is text inside W.
- **Main confound & control:** probe supervision leaks task labels. Train probes on a disjoint repo/bug split; report probe val accuracy separately from arm performance; include a shuffled-probe-weights control.
- **Effort:** medium (1–2 weeks incl. label design and activation capture; sklearn probes themselves are trivial). Needs A under HF (or post-hoc re-prefill with hooks).
- **Support:** Zhu et al. [2402.18496] (belief decodable >80%, steering causal), Bortoletto [2406.17513] (methodology + brittleness warning), Gurnee & Tegmark [2310.02207] (probe recipe), Shai [2405.15943] (why residual stream should hold the epistemic state), Apollo [2502.03407] + Anthropic sleeper-probe blog (probes generalize off-distribution well enough to be useful monitors).

### Rank 4 (optional) — Arm L-STEER: steering-vector handoff
- **Transferred:** 1–k residual-stream steering vectors distilled from A's episode (RepE contrast pairs: activations on "briefing successor honestly" vs neutral; or mean activation deltas à la State Delta [2506.19209]), added into B's forward pass at chosen layers via hooks.
- **Capacity:** tiny and cleanly bounded (k × d_model), sits at the far-left of the capacity curve.
- **Confound/control:** steering perturbs fluency/behavior globally, not informationally — control with random directions of matched norm; expect weak gains. Rank last: least supported as a *communication* mechanism (2501.14082 is closest, but its gains came in single-forward-pass settings, not long agentic runs).
- **Effort:** low-medium. **Support:** RepE [2310.01405], Ramesh & Li [2501.14082], SDE [2506.19209].

**Recommended package:** L-KV + L-THOUGHT as the two "true latent" arms (they bracket the capacity spectrum: KV = maximal bits/slot, thoughts = one vector/slot), plus L-PROBE as the science bridge to the existing belief-ledger arms. Report both slot- and bit-ledgers for every arm; the honest headline comparison is the capacity–performance *curve*, not a single point, since the literature (C2C, LatentMAS, gist tokens [2304.08467]) consistently shows latent slots carry several text-tokens' worth of information.

**Flag for the limitations section:** per "When Latent Agents Lie" [2606.28958] and LCGuard [2605.22786], KV handoff is an unauditable channel — text-level judging of the artifact has no latent equivalent, so any "artifact quality" secondary metrics must be dropped or replaced by probe-based monitors for the latent arms.
