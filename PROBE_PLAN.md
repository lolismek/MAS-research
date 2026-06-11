# Latent Knowledge-Transfer Probe (pre-mini-CORAL)

## Context — read this first, the session that produced it is gone

**Project:** MAS-memory-research, branch `open-ended-discovery` (orphan branch, currently contains only `.gitignore`; all prior failure-mode experiments live on `main`). New direction: multi-agent systems for open-ended discovery, following **CORAL** (arXiv 2604.01658, `references/CORAL.pdf`), and testing whether **latent mechanisms** improve it. User's broad research notes: `references/MAS with latent communication-2.pdf`.

**CORAL in one paragraph:** autonomous agents (full coding agents in isolated git worktrees) iteratively improve a solution to an open-ended optimization task (plan → edit → `coral eval` → reflect). They coordinate *only* through a shared text file system: `attempts/` (auto-written JSON per eval: commit hash, score, status, parent_hash), `notes/` (free-form markdown insights, agent-written), `skills/` (reusable scripts + descriptions). No direct messaging. Heartbeats force memory formation: reflect (note after every eval), consolidate (every 10 evals, notes→synthesis/skills), pivot (after 5 stale evals). Ablations show the knowledge artifacts are causal for performance; on circle packing, 100% of attempts that read shared knowledge improved (Read→Impr, Table 5).

**Hypothesis (converged through discussion):** notes are a *lossy channel*. When agent A writes a 150-word note after a 30k-token trajectory, everything not verbalized is lost; reader B re-encodes the prose inside its own context. Latent augmentation — shipping A's hidden states alongside the note text — should make knowledge transfer less lossy. Smaller models write worse notes, so the headroom is *larger* at our scale (Qwen3-8B vs the paper's Opus 4.6).

**Scope decisions already made (do not relitigate):**
- v1 targets **notes only**. Skills stay textual/executable (a skill's value is symbolic+runnable; "latent skills" = trained-prefix territory = v2). Attempts/code transfer stays git-based (lossless already).
- Latents are a **transport layer, invisible to agents**: agents read/write text exactly as in CORAL; the harness attaches/injects latent sidecars (`note.md` + `note.md.latent`). Agent autonomy and decision-making identical across conditions.
- **Training-free v1.** Same checkpoint for writer and reader (states only meaningful within one model's representation space). Trained compressor (gist/ICAE-style) is the designated v2 fallback if training-free fails.
- **Before building mini-CORAL, run this probe**: a single-step transfer test that asks whether cross-context state injection helps *at all*. The user explicitly wants the probe first, with **all arms specified** so they can choose which to implement.

**Fixed choices (user-confirmed):**
- Task: **circle packing** — n=26 circles in unit square, maximize sum of radii (AlphaEvolve task; CORAL SOTA 2.6359). Chosen because: highest knowledge usage of all 11 CORAL tasks (0.64 artifacts/attempt, 55% access, Read→Impr 100%), trivial CPU evaluator (seconds), known external baselines.
- Model: **Qwen3-8B** (`Qwen/Qwen3-8B`): 36 layers, hidden 4096, 32 Q heads / 8 KV heads (GQA), head_dim 128, QK-norm, 32k native context, transformers ≥ 4.51. Fallback Qwen3-4B (same layer count, hidden 2560) for debugging.
- Compute: **cloud GPU rented by Claude/user** (Lambda/RunPod-style, 1× A100-80GB or similar). Budget target: tens of dollars (~25–35 GPU-hours total).

**Reference code (verified to exist, both Apache 2.0):**
- Evaluator: `github.com/skydiscover-ai/skydiscover` → `benchmarks/math/circle_packing/{evaluator.py, initial_program.py, config.yaml}`. Validates boundaries (1e-6 tol) + overlaps, returns `sum_radii`/`combined_score`. CORAL repo (`github.com/Human-Agent-Society/CORAL`) lists circle_packing as an example task and is the reference for note/heartbeat prompt wording (paper Appendix C.1).
- Injection reference: `github.com/Gen-Verse/LatentMAS` (supports Qwen3-4B/8B/14B, HF transformers). Key files: `models.py` (`generate_latent_batch_hidden_state()` — last-token hidden state extraction; feeds hidden states back as `inputs_embeds`), `methods/latent_mas.py` (KV slicing `_slice_tensor`, cache_position arithmetic for RoPE alignment, attention-mask extension for cached prefixes).

---

## The probe

**Question:** given the *same* reader context and the *same* note text, does attaching the writer's latent states improve the reader's next attempt?

**Unit of measurement:** a "transfer episode" = (reader context B at some mid-trajectory state, a note written by a different trajectory A, one injection condition) → B generates one full attempt (reasoning + code edit) → run the real grader → record score delta vs. B's current best. Paired design: identical B context and sampling seed across all arms; only the injected payload differs.

### Arms (user will choose which to implement; specify all)

| # | Arm | Payload added to note text | Selection needed | Source of method |
|---|-----|---------------------------|------------------|-------------------|
| 1 | **Text-only** (baseline) | none | — | CORAL as-is |
| 2 | **Rolled latent thoughts** | m=8 synthetic states: A's last-token last-layer hidden state fed back as `inputs_embeds`, rolled forward m steps at note-write time | none (m fixed) | LatentMAS |
| 3 | **Note-suffix KV** (user's proposal, lead candidate) | A's states for the note's own tokens — contiguous suffix of A's trajectory at note-write time. Same words the reader sees, but contextualized by A's whole trajectory | none (natural boundary = the note-writing turn) | this project |
| 4 | **Attention-selected trajectory KV** | top-k trajectory positions ranked by attention mass that A's note tokens placed on them (sink-masked, mid-to-late layers, max over heads — SnapKV-style) | k (sweep 64/128/256) | SnapKV/H2O recipe |
| 5 | **Raw segment as text** (ceiling control) | the plain text of A's trajectory window since last eval (token-unconstrained; also a matched-budget truncated variant) | window = since-last-eval | control |

**Why arm 5 is the most important line in the table:** it disambiguates outcomes. 3/4 ≈ 5 at fewer tokens → latents are a compression win. 2/3/4 ≈ 1 while 5 > 1 → information exists but training-free injection can't deliver it → go to trained compressor v2. 5 ≈ 1 → trajectory residue isn't worth transferring on this task → rethink hypothesis before building anything.

**Design fork (apply to arms 2–4):** inject **alongside** the note text (default; reader can still quote exact numbers) vs. **in place of** it (compression condition, matched token budget). Implement alongside first; in-place is a cheap toggle.

### Injection mechanics — two implementation levels

- **Level (i) — embedding-space injection (v0, use for all latent arms):** store *last-layer* residual-stream states for the chosen positions; at read time, feed them as `inputs_embeds` at B's positions — the model computes K/V itself, RoPE and GQA handled automatically, no cache surgery. This is exactly LatentMAS's validated mechanism; adapt their code.
- **Level (ii) — cache-space injection (fidelity upgrade, only if (i) shows nothing for arms 3/4):** store *per-layer* residual states; reader-side, for each layer run input_layernorm → W_k/W_v → QK-norm → RoPE at B's positions, write into a `DynamicCache` at reserved positions, extend attention mask. Preserves A's per-layer representations instead of letting B's layers re-process. More surgery; LatentMAS's cache_position/mask code is the starting point.

**Implementation notes (hard-won during discussion, keep):**
- Attention scores for arm 4 are not available from FlashAttention/SDPA. Compute them explicitly only for the note-writing turn: q·k matmul from cached states (O(m·N·d) per layer, once per note). Do NOT force eager attention globally.
- Mask attention sinks (BOS/first tokens) before ranking in arm 4; rank local window and long tail separately (recency bias).
- Hidden states per layer come from one extra forward pass with `output_hidden_states=True` over the relevant span at note-write time (capture is post-hoc; trajectory generation itself can run with fast kernels).
- Sidecar format: safetensors file next to the note markdown; metadata JSON (positions, layers, arm, writer trajectory id, token ids for debugging).

---

## Pipeline (phases, each with a gate)

### Phase 0 — environment + task + model sanity (gate: model can improve the seed at all)
1. Provision cloud GPU (1× A100-80GB class). `uv`/conda env: torch, transformers ≥4.51, safetensors, accelerate. Download `Qwen/Qwen3-8B`.
2. Port circle-packing evaluator: vendor `evaluator.py` + `initial_program.py` from SkyDiscover into `probe/task/`; strip framework deps; wrap as `evaluate(program_path) -> {sum_radii, valid, error}` with subprocess + timeout (grader isolation, same spirit as CORAL's `.coral/private/`).
3. Minimal single-agent loop (no multi-agent, no heartbeats yet): system prompt adapted from CORAL's single-agent template (Appendix C.1.1) — orient, propose code edit, eval, reflect-note after every eval (reflect prompt adapted from C.1.2). Plain text, ~12–15 evals per trajectory. Qwen3 thinking mode ON for proposal turns (config flag to compare).
4. **Gate:** ≥ ~10% of evals improve best score across 3 pilot trajectories. If flat: try better seed prompt, thinking mode, Qwen3-14B, before proceeding. If nothing improves the seed, the probe is moot — stop and reassess.

### Phase 1 — trajectory bank with state capture
1. Run ~20 single-agent trajectories (different seeds/temperatures), each 12–15 evals, each producing reflect-notes. Log every token, eval event, and note event (JSONL per trajectory).
2. At each note event, capture and store all candidate payloads at once (they share the forward passes): last-layer states for note tokens (arm 3-i), per-layer states for note tokens (arm 3-ii, cheap to add), m=8 rolled states (arm 2), attention-ranked trajectory positions + their states (arm 4), since-last-eval text window (arm 5).
3. Curate ~40–60 transfer episodes: (B context, A note) pairs where A ≠ B's trajectory, A's note is relevant (B hasn't already found A's insight), and B has headroom (B's best < A's best, or B plateaued). Selection scripted + manually spot-checked; freeze as `probe/episodes/`.

### Phase 2 — injection module + coherence checks (gate: injection is non-destructive and attended)
Built before the arms run; this is the user's stated first concern ("test that the injection is coherent").
1. Implement level (i) injection; unit tests: round-trip (inject states extracted from B's own context at the same positions → generation distribution ≈ unchanged), positional correctness, mask correctness.
2. **Coherence battery** on ~10 episodes: (a) fluency — injected-condition continuations remain well-formed code/reasoning, no perplexity blow-up vs. baseline; (b) attention diagnostic — B's generated tokens place non-trivial attention mass on injected slots (if ~zero, arms 2–4 will collapse to arm 1; report and stop early); (c) needle test — A's trajectory contains a planted fact absent from the note text (e.g., "approach X failed"); measure whether B's plans reflect it above chance in injected vs. text-only conditions.
3. **Gate:** (a) passes and (b) shows nonzero attention. (c) is informative, not gating.

### Phase 3 — run the arms
- For each episode × each implemented arm × 3 samples (temp ~0.7, paired seeds): build B's context (B trajectory prefix + note-read event + payload per arm), generate one attempt, run grader.
- ~50 episodes × 5 arms × 3 samples ≈ 750 generations × ~2–3k tokens. With per-episode KV reuse of the shared prefix, est. ~12–18 GPU-hours.

### Phase 4 — analysis + writeup
- **Primary metric:** paired score delta of next attempt vs. arm 1 (per-episode pairing; bootstrap CIs over episodes, not samples).
- **Secondary:** fraction of attempts improving B's best ("single-step Read→Impr"); validity rate (does injection increase broken-code rate?); tokens consumed per condition.
- **Diagnostics:** attention mass on injected slots vs. outcome; arm-4 k-sweep; alongside vs. in-place.
- Deliverable: `probe/REPORT.md` with the decision table — which arm (if any) carries signal → build mini-CORAL with that arm / go to trained-compressor v2 / kill the latent-notes hypothesis.

---

## Repo layout (all under `~/MAS-memory-research`, branch `open-ended-discovery`)

```
probe/
├── task/            vendored circle-packing evaluator + seed (from SkyDiscover, Apache 2.0 — keep LICENSE note)
├── agentloop/       minimal single-agent loop (HF transformers, Qwen3-8B), trajectory JSONL logging
├── capture/         note-event state capture (all payload types), sidecar safetensors writer
├── inject/          level-(i) embedding injection (+ level-(ii) cache injection, stretch), coherence tests
├── episodes/        frozen (B context, A note) pairs
├── arms/            arm runners + paired sampling harness
├── analysis/        metrics, bootstrap, plots, REPORT.md
└── env/             setup script for cloud GPU (uv env, model download, smoke test)
```

`.env` (already gitignored) holds any API keys; cloud-GPU SSH details go in `env/README.md`, not committed.

## Cost/runtime estimate
Phase 0–1: ~8–12 GPU-h (trajectory bank dominates). Phase 2: ~1–2 GPU-h. Phase 3: ~12–18 GPU-h. Total ≈ 25–30 GPU-h ≈ **$30–60** on an A100-class rental. Mac (MPS) is fine for writing/debugging all code with Qwen3-4B at tiny scale before renting.

## Risks
- **Model too weak on task** → Phase 0 gate; escalate prompt/thinking-mode/model-size before concluding anything.
- **Attention ignores injected slots** (the central scientific risk) → Phase 2 diagnostic catches it for ~$2 instead of after the full run; outcome is itself a publishable negative datapoint for training-free transfer in agentic loops.
- **Confound: latent arms see more information AND more capacity** → arm 5 (text ceiling) + matched-token in-place variants isolate channel effect from information effect.
- **Episode curation bias** → freeze episodes before running any latent arm; same episodes for all arms.
- Known open question to flag in REPORT: training-free cross-*context* injection is untested territory (CIPHER/DroidSpeak/KVComm/LatentMAS are all short-horizon or sequential-handoff settings).

## Verification
- Evaluator: reproduce seed-program score from SkyDiscover; hand-craft a known-valid packing and a known-overlapping one, assert accept/reject.
- Injection: round-trip unit test (above) must pass; needle test gives a human-readable sanity signal.
- End-to-end: one full episode through all implemented arms, eyeball the 5 generations side by side before launching the batch.

## Explicitly out of scope (v2+, do not build now)
mini-CORAL multi-agent harness; heartbeat machinery beyond the reflect prompt; latent skills (trained prefixes / flashmem→extra-mem extension); trained compressor (gist/ICAE); commit-checkout latent attachments; heterogeneous-model translation.
