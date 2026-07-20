# SyncHandoff — Lab Benchmark Plan

**Date:** 2026-07-20 · **Branch:** `lab-test` · **Status:** proposed, pending pilot gates

A lab benchmark for the isolated **agent A → agent B handoff edge**, built by splitting
SyncMind/SyncBench out-of-sync-recovery episodes at a communication point. The purpose is to
measure how much of A's *useful work* — facts, verified findings, ruled-out branches,
calibrated uncertainty — different **handoff protocols** (the duet arms: vanilla, SOP, DOWN,
belief board, etc., and later latent variants) get across the channel, as measured by B's
downstream success.

---

## 0. One-page summary

**The question.** When agent A has done real investigative work and must hand its findings to
a fresh agent B through a bounded channel, how much of A's *epistemic state* — facts learned,
hypotheses held, hypotheses ruled out, confidence, errors — survives the handoff, and does the
form of the handoff (plain note vs. SOP vs. confidence-annotated vs. belief ledger) change B's
downstream success?

**The substrate.** SyncBench (arXiv 2502.06994): 24,332 instances from 21 real Python repos.
Each instance is an "out-of-sync" state: a collaborator silently changed a function (reconstructed
from real git history); the agent must localize the stale code, diagnose the change, and repair
the repo until the unit tests pass. Ships with Docker environments, executable tests, and ground
truth (true update, correct file/function). Dataset on HuggingFace (`xuehang/SyncBench`, including
a curated 300-instance eval subset), harness built on OpenHands. Verified released.

**The construction.** Split each episode in two:

1. **Phase 1 (A):** A explores the broken repo for k turns — *chosen so A usually has NOT
   solved it*. Its trajectory is a genuine partial belief state.
2. **Handoff:** A emits a handoff under the protocol being tested, under a token budget.
   A's context is destroyed.
3. **Phase 2 (B):** a fresh agent gets only [task + handoff] and a reduced turn budget, and
   must finish the recovery. Scored by the executable tests + localization ground truth.

Phase-1 trajectories are generated **once and frozen**; every protocol and budget reuses the
same cached trajectories → paired comparisons, low cost.

**The brackets.** Every instance is run under: **floor** (B gets nothing), **ceiling** (B gets
A's full transcript), **oracle** (B gets a ground-truth note built from the gold answer), plus
each arm in between. Headline: fraction of the ceiling−floor gap each arm recovers, per unit
of handoff budget.

**The primary claim.** Handoff protocols that carry epistemic structure (typed findings,
confidence, belief ledgers) recover more of the ceiling−floor gap than a plain note at the
same budget — i.e., more of A's *useful work* survives the channel. Secondary, post-hoc:
instances where A's hypothesis was *wrong* form natural false-belief bins (does B inherit or
recover?) — kept as a robustness/diagnostic cut, not a headline (§5.3).

**Decision rule (go/no-go).** A ~30-instance pilot runs the three brackets on our backend
(Qwen3.6-35B-A3B via Tinker). If ceiling − floor spread on {SR, localization, turns} is
material, we build the full thing. If B fails even with the full transcript, the substrate is
too hard for our model and we fall back to FANToM (see §11).

---

## 1. Motivation and lineage (why this benchmark)

Our field studies (AutoGen split4, Magentic, ChatDev) repeatedly showed the same failure class:
one agent knows something and it dies at the boundary — the bare "225" published without
provenance, verified facts restated as guesses, wrong assumptions inherited downstream. The
duet harness (branch `multi-benchmark-eval`) already implements seven handoff protocols ("arms")
that manipulate exactly this boundary. What is missing is a **lab instrument**: a task where

- A must do real work (so its belief state is non-trivial),
- the A→B channel is a single bounded artifact (so arms have something to transform),
- B's outcome is verifiable without an LLM judge,
- and there is headroom between "no handoff" and "perfect handoff" (so arms can be discriminated).

What we tried and rejected:

| Option | Why rejected |
|---|---|
| Synthetic generation (`handoff/PLAN.md`) | Manufacturing a *credible partial belief state* for A symbolically is the hard part; high risk of a sterile benchmark |
| EnactToM | Dataset unreleased; embodied (Habitat) confounds; no discrete note edge; floor-effected (0% for all models on hard split) |
| FANToM / OpenToM | Usable (kept as fallback) but A's "work" is just reading; content is conversational beliefs, far from our agentic setting |
| InformativeBench (Schedule) | Exact-scorable but payload is bare calendar facts — no hypotheses, no confidence, no false beliefs |
| FriendsTV | Contaminated (models know Friends), judge-scored |

SyncHandoff keeps what each of these lacked: **real work → real partial beliefs → one bounded
channel → executable verification → natural false beliefs.**

Honest scope note: like everything above, this measures **epistemic transmission** (facts +
hypothesis status + confidence + provenance), not nested-belief ToM. But the false-belief bins
give a *functional* second-order test — B must represent "A believed X; X may be false" — which
is stronger than the QA-style ToM benchmarks' literal probes.

---

## 2. Substrate primer: SyncBench / SyncMind

- **Instance** = a repo snapshot where one function was updated by a "collaborator" (real commit
  pairs mined from git history), the agent's dependent code is now stale, and a test suite fails.
  Ground truth: the true update, the correct file and function. Two variants: **Callee** (the
  updated function itself must be fixed/understood) and **Caller** (the agent's code calls the
  updated function). We start with **Callee** (localization semantics are cleaner); verify both
  on download.
- **Environment**: Docker per repo, built from the repo's setup files; tests run with a timeout.
- **Harness**: OpenHands (CodeActAgent) with an eval script; LLM backend is config-driven
  (LiteLLM), so it can point at any OpenAI-compatible endpoint — including our Tinker proxy.
- **Published difficulty** (30-turn solo budget): SR ranges from ≤4% (Llama-3.1) to ~25–28%
  (Claude-3.5-Sonnet). Also: agents rarely seek help (ASR ≤ 4.9%) — independent evidence of
  the transmission-failure thesis in the SWE setting.
- **Scale**: 24,332 instances total; curated `syncbench_300` eval subset (150 callee + 150
  caller). We will subsample our own working set (§6).

---

## 3. Episode anatomy

```
┌────────────────── Phase 1 (frozen once) ──────────────────┐
│ Agent A: task prompt + repo access (OpenHands tools)      │
│ Runs exactly k turns (k calibrated in pilot, §6).         │
│ Trajectory cached: every thought/action/observation.      │
└──────────────┬────────────────────────────────────────────┘
               │  HANDOFF: protocol P transforms (trajectory → artifact),
               │  artifact ≤ token budget W. A's context destroyed.
┌──────────────▼────────────── Phase 2 (per arm) ───────────┐
│ Agent B (fresh): task prompt + artifact + repo access.    │
│ Turn budget m < k + m_total. Must finish the recovery.    │
│ Scored: unit tests (SR), localization (LA), turns.        │
└───────────────────────────────────────────────────────────┘
```

Fixed ecological facts (mirroring duet's locked decisions): A knows a handoff will happen
(the harness forces it at turn k — no strategic choice about *whether*); A never sees B's
budget or identity; the artifact is a normal handoff, its *form* is decided entirely by the arm.

**Budgets.** One default operating point: k (A's turns) and m (B's turns) set by pilot;
handoff budget W ≈ 300 tokens soft / 500 hard-truncate (logged as covariate). A budget-sweep
(W ∈ {100, 300, 1000, full}) is a phase-2 experiment producing fidelity-vs-capacity curves;
not part of the core sweep.

---

## 4. Conditions

### 4.1 Brackets (controls, run on every instance)

| Bracket | B receives | Establishes |
|---|---|---|
| **floor** | nothing (task only) | what B can do alone at budget m |
| **ceiling** | A's full Phase-1 transcript | everything A's work could possibly contribute |
| **oracle** | ground-truth note (true update + file/function, templated from gold) | B's *utilization* ceiling — separates "A didn't find it" from "B can't use it" |

The oracle bracket is cheap (gold ships with every instance) and diagnostic: if oracle ≫
ceiling, A's k turns didn't surface the answer (raise k); if oracle ≈ floor, B can't act on
even perfect information (substrate too hard → fallback).

### 4.2 Arms (the science; ported from duet `harness/arms.py`)

| Arm | Handoff artifact |
|---|---|
| `vanilla` | free-text note A writes at turn k, budget W |
| `full` | full transcript, truncated-from-the-front to W (naive baseline distinct from ceiling) |
| `sop` | MetaGPT-style typed sections: FINDINGS / EVIDENCE / VERDICT / NEXT_STEPS |
| `down` | vanilla note + B may raise ONE bounded clarification Q, at B's own judgment (duet dropped the θ-confidence gate: it never fired — models always self-report high confidence) |
| `board` | belief ledger A maintained *during* Phase 1 via add_belief/revise_belief tools; ledger is the artifact |
| `extract` | observer LLM reads A's trajectory post-hoc and writes the ledger (no in-loop tools) |
| `board_inert` | A has the board tools but the ledger is NOT transmitted (confound control for the tool-use effect on A's own exploration) |

Note on `board`/`board_inert`: these change Phase 1 itself (A has extra tools), so they need
their own frozen Phase-1 trajectories — one extra generation pass, still frozen and reused.
All other arms share the single vanilla Phase-1 cache.

Phase-2 (later): latent handoffs — KV-cache/activation transfer between A and B. Requires
identical open-weights model both sides; our Tinker Qwen3.6 backend satisfies this. Out of
scope for v0 but the interface (artifact = opaque blob + loader) is designed for it now.

---

## 5. Metrics

### 5.1 Functional (headline, judge-free)

Primary hypothesis, stated once: **GR(sop / down / board / extract) > GR(vanilla) at equal
budget W**, with the oracle bracket bounding how much of any shortfall is B-side utilization
rather than channel loss.

- **SR** — unit tests pass (SyncMind's own success criterion).
- **LA_file / LA_func** — B localizes the correct file / function (partial credit; much higher
  statistical resolution than SR at low base rates → co-headline).
- **Turns-to-success** — among successes; efficiency of the handoff.
- **Gap recovery** — primary comparison statistic:
  `GR(arm) = (score(arm) − score(floor)) / (score(ceiling) − score(floor))`,
  computed per-metric on the paired instance set.

Statistics: all arms are paired on the same frozen Phase-1 trajectories → McNemar tests on
SR/LA, paired bootstrap CIs on GR. Each Phase-2 condition run with n=2–3 seeds (temperature
sampling) to average B-side variance.

### 5.2 Intrinsic probe battery (secondary, mechanism diagnostic)

Immediately after receiving the handoff — before B touches the repo — B answers a fixed probe
battery: *What changed? Where? What did your predecessor rule out? What is still untested?
What was the predecessor confident about vs. guessing?* Graded by LLM judge against (a) ground
truth and (b) A's actual frozen trajectory. Two derived scores:

- **Transmission fidelity** — probes correct w.r.t. what A actually knew/believed.
- **Confabulation rate** — probes asserting beliefs present in neither the handoff nor A's
  trajectory (FANToM-style consistency requirement; penalized).

These never headline (judge-based) but explain *why* an arm won or lost: e.g., ledger arms may
raise fidelity without raising SR (utilization bottleneck), or raise SR precisely on instances
where fidelity improved (the mechanism story).

### 5.3 Belief-state bins (secondary, post-hoc robustness cut)

Not a headline — a diagnostic slicing of the primary results. Label each frozen Phase-1
trajectory (LLM labeler + hand-check of a slice):

- **Bin T** — A's final working hypothesis was correct (right localization/diagnosis).
- **Bin F** — A held a wrong hypothesis at turn k (mislocalized, wrong diagnosis).
- **Bin ∅** — A had no committed hypothesis.

Primary analysis runs on the full set; Bin T (and ∅) is where most data lives and where the
GR hypothesis is tested. Bin F is reported as a robustness cut: per-arm **inheritance rate**
(B commits to A's wrong hypothesis) and **recovery rate**. Interesting if epistemic-status
arms (`down`, `board`) cut inheritance — they transmit *that a claim was a guess* — but the
bin is small and uncontrolled, so treat any effect as exploratory, to be confirmed separately
if it looks dramatic. No selection engineering is done to inflate Bin F (§6).

---

## 6. Instance selection and calibration

1. **Download** `syncbench_300` + a slice of the 24k set; verify Callee/Caller semantics and
   instance fields; build Docker envs for a subset of repos (start with the repos SyncMind's
   own eval used — envs known to build).
2. **Difficulty skew**: prefer instances at the easier end (published solves by mid-tier
   models), because B runs on a reduced budget and our backend is mid-tier. A benchmark our
   model scores 0% on discriminates nothing.
3. **k calibration** (pilot, gate G2): run A at k ∈ {5, 8, 12} on ~30 instances. Choose k
   where A has *engaged but usually not solved*: target ≈ 60–80% of trajectories with
   non-trivial findings and < 30% already-solved. Verify post-hoc from the frozen trajectories.
4. **Working set**: generate Phase-1 on ~300 candidate instances at the chosen k; label bins;
   select **~120–150 frozen instances** for repo diversity and a spread of trajectory quality
   (A found much / some / little — the primary GR analysis needs variance in what there is to
   transmit). Bins are recorded, not engineered: whatever Bin F falls out is reported as-is.
   Freeze forever (`phase1_frozen/` + manifest with hashes).

---

## 7. Engineering plan

**Principle: the arms are the science; the harness is whichever one already runs the substrate.**
We do NOT teach duet to run Docker. We port duet's arm seam into SyncMind's OpenHands harness.

Components (new code in `synchandoff/`):

1. **`phase1_runner.py`** — wraps SyncMind's run_infer with a hard turn cap k; serializes the
   full trajectory (events JSONL) to `phase1_frozen/<instance_id>/<arm_family>/traj.jsonl`.
   Two arm families of Phase-1: `plain` (shared by vanilla/full/sop/down/extract + brackets)
   and `board` (A gets add_belief/revise_belief tools; shared by board/board_inert).
2. **`handoff/arms.py`** — port of duet's arm transformations, adapted to trajectory input:
   each arm = `f(frozen_trajectory, gold=None) → artifact string (≤ W)`. Oracle bracket is
   `f(gold)`. Pure functions over cached data → all artifacts for all arms are precomputed
   offline and cached (`artifacts/<instance>/<arm>.txt`) before any Phase-2 spend.
3. **`phase2_runner.py`** — launches fresh OpenHands agent with prompt = task + artifact,
   turn cap m; DOWN's one clarification Q/A is the only arm needing A-side liveness — answered
   by an LLM prompted with A's frozen trajectory (predecessor-simulacrum), same trick duet uses.
4. **`probes.py`** — pre-repo probe battery + judge; `bins.py` — trajectory labeler.
5. **`score.py`** — SR/LA/turns from SyncMind's eval output + GR computation + paired stats;
   `REPORT.md` generator.
6. **Backend**: OpenHands LLM config → our OpenAI-compatible proxy → Tinker Qwen3.6-35B-A3B.
   Known risk: CodeActAgent prompting is tuned for frontier models; may need a lighter action
   format for Qwen (checked at gate G1).

Standing constraints honored: all model runs on bren / via Tinker (never local on the Mac);
Claude smoke-tests only (single instances, $5-class spend); **full batches are launched by
the user**.

---

## 8. Pilot and decision gates

| Gate | Test | Pass condition | Fail action |
|---|---|---|---|
| **G1 — plumbing** | 2 instances end-to-end: env builds, Qwen acts in OpenHands, tests execute, trajectory serializes | all mechanical steps work | fix or swap agent scaffold (e.g., minimal custom loop instead of CodeActAgent) |
| **G2 — headroom** | ~30 easy-skewed instances × {floor, ceiling, oracle} at chosen k, m | ceiling and oracle beat floor by a material margin on SR or LA (target: ≥ 15 points on LA_func or ≥ 10 on SR) | try easier subsample / larger m / stronger model for B once; else **fallback to FANToM** (§11) |
| **G3 — k calibration** | A-trajectory audit at candidate k values | 60–80% of trajectories with non-trivial findings, < 30% already solved | adjust k (this gate is about the primary GR analysis having something to transmit; bin composition is recorded, not gated on) |
| **G4 — arm sanity** | vanilla + one ledger arm on the G2 set | vanilla lands between floor and ceiling; arms produce well-formed artifacts | debug arms before full sweep |

Gates G1–G4 are cheap (≈ 30 instances × ≤ 6 conditions × ~10–15 turns). Only after G4 does
the user launch the full sweep.

---

## 9. Full experiment matrix and cost envelope

Core sweep (v0): **~130 frozen instances × (3 brackets + 7 arms) × 2 seeds** of Phase 2, plus
2 Phase-1 generation passes (plain + board families) over ~300 candidates.

Rough token math (Qwen via Tinker, self-metered as usual): a 10–15-turn OpenHands turn cycle
runs ~3–8k tokens; call it ~75k tokens per Phase-2 episode → ~2,600 episodes ≈ 200M tokens
total across the sweep. At Tinker Qwen rates this is tens of dollars, not hundreds — but the
pilot (G1–G4, ≈ 5–8M tokens) will replace this estimate with a measured one before anything
big launches. Phase-1 is amortized (run once, reused by every arm, budget, and future latent
experiment).

Wall-clock: Docker test execution dominates (up to 600 s timeouts); run with SyncMind's
worker parallelism on bren.

---

## 10. Threats to validity

1. **Capability floor** (main risk): Qwen3.6-35B may fail even with perfect information.
   Managed by: easy-skewed subsample, LA as co-headline (partial credit), oracle bracket
   isolating utilization, and gate G2 as a hard go/no-go.
2. **k mis-calibration**: too low → empty belief states (arms indistinguishable); too high →
   A solved it (every arm transmits the answer; ceiling collapse). Managed by G3 + post-hoc
   trajectory audit; k is per-benchmark, not per-instance, to keep the design simple — accept
   the residual variance, it's paired out.
3. **Repo contamination**: models know these public repos. Weak threat: success requires
   repairing a *constructed* stale state, not recalling code; the floor bracket measures any
   residual advantage directly.
4. **Judge dependence**: confined to secondary metrics (probes, bin labels). Bin labels get a
   hand-checked slice (20 trajectories, stratified) before the ToM claims are made.
5. **Arm-prompt confounds**: arms differ in prompt length/shape, not just content. Mitigated
   as in duet: prompt-diff audit + `board_inert` control + fixed W budget across arms.
6. **DOWN's interactive Q/A**: the predecessor-simulacrum answers from the frozen trajectory —
   it can't know things A never wrote down. This is faithful to the protocol (a real
   predecessor would be gone too) but log Q/A pairs and audit a slice.
7. **OpenHands version drift**: pin OpenHands + SyncMind commits and Docker image digests in
   the manifest; frozen trajectories carry the pin.

---

## 11. Fallback

If G2 fails (no headroom on this substrate with our backend), fall back to **FANToM** as the
lab bench: conversations chunked into files → A reads under tool budget → note → B answers the
fact/belief/answerability battery (exact + F1 scoring, guaranteed floor since B never sees the
conversation). Weaker "A did work" story, but guaranteed spread and near-zero engineering (it
fits duet's existing read_file relay directly). OpenToM as a second bench under the same
converter. The arm seam and probe designs above transfer unchanged.

---

## 12. Order of work

1. **[gate]** Download SyncBench, verify fields/semantics, build 2 Docker envs, wire Qwen
   backend into OpenHands → **G1** (Claude: build + smoke).
2. Subsample easy-skewed candidates; `phase1_runner.py`; run k-sweep on ~30 → **G2, G3**
   (Claude smokes 1–2 instances; user launches the 30-instance pilot batches).
3. **[review gate]** Pilot report: headroom numbers, chosen k/m/W, bin census. Decision:
   proceed / adjust / fallback.
4. Port arm seam (`handoff/arms.py`), artifact precompute, `phase2_runner.py`, probes →
   **G4** smoke.
5. Phase-1 generation over ~300 candidates (both arm families, user-launched); bin labeling;
   freeze the ~130-instance working set + manifest.
6. **[user launches]** Full core sweep (§9). Claude: scoring, stats, REPORT.md.
7. Phase-2 experiments (later): budget sweep W-curves; latent KV handoff arms.

---

## Appendix A — File layout

```
synchandoff/
  PLAN.md                  # this file
  env/                     # backend config, OpenHands/SyncMind pins, Docker notes
  selection/               # candidate lists, difficulty skew, bin census, frozen manifest
  phase1_runner.py  phase2_runner.py
  handoff/arms.py          # ported arm seam (pure: trajectory → artifact)
  probes.py  bins.py  score.py
  phase1_frozen/<id>/<family>/traj.jsonl
  artifacts/<id>/<arm>.txt
  runs/<sweep>/...         # Phase-2 outputs, eval summaries
  REPORT.md
```

## Appendix B — Terminology map (duet ↔ here)

| duet (multi-benchmark-eval) | SyncHandoff |
|---|---|
| RELAY shift boundary, forced note | turn-k handoff, forced artifact |
| note_yield axis | artifact budget W (covariate + phase-2 sweep) |
| empty-note floor / gold-note oracle / full-trace topline | floor / oracle / ceiling brackets |
| channel recall × utilization | transmission fidelity (probes) × oracle-bracket utilization |
| arms.py seam | handoff/arms.py (same 7 arms, trajectory-input) |
