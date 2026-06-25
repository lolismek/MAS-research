# Plan: Multi-Benchmark × MAS-Framework × Add-on Sweep

## Context

We have a v0 **shared belief-state board** — a scratchpad where MAS agents sincerely record their *current internal state and what motivates each action*, so teammates (and the selector) can read state that never makes it into polished final messages. So far it's been validated on exactly **one cell**: GAIA × AutoGen GroupChat × {vanilla, belief-board}, on the `eval-clean` branch.

The goal of this branch (`multi-benchmark-eval`, currently an empty orphan) is to turn that one cell into a principled **sweep**: does the belief board *generalize* across benchmarks and MAS frameworks, and does it *beat* the other "add-on" coordination/memory methods from the literature? The headline is **multi-axis**, not just accuracy (per user): we want the board to improve (1) **accuracy**, (2) **honesty** — admitted failure ("we couldn't verify this") *instead of* confident hallucination, and (3) **efficiency** — fewer model calls per success. (2) is the belief board's core value proposition: exposing true uncertainty should convert confident-wrong answers into honest abstentions. This connects directly to the prior `no_answer→correct` and relational-misalignment work.

**Decisions locked with the user:**
- First expansion: **deepen on AutoGen-GC** (add benchmarks + the full baseline-arm set on the framework we already have working) before adding framework variance.
- Priority: **multi-axis improvement** — accuracy, admitted-failure-over-hallucination, calls-per-success (and others as they emerge).
- Embodied track (Overcooked/TDW-MAT/C-WAH): **deferred**, pilot Collab-Overcooked later; normal track first.
- Model backend: **research-determined** → Tinker OpenAI-compatible endpoint (see Model Backend section).

## Verified reference facts (don't re-litigate)

| Ref | Actual identity | Role in this project |
|---|---|---|
| **arxiv 2602.03036** | **"LatentMem: Customizing Latent Memory for MAS"** (Fu et al.) | NOT a baseline to build. It's the **source** for the **ChatDev-memory** & **MetaGPT-memory** baselines (defined/benchmarked in its appendix) and the **CAMEL** config to mirror. LatentMem *itself* needs a trained composer (LMPO) → **defer** bucket. |
| **arxiv 2604.01658** | **"CORAL: Towards Autonomous Multi-Agent Evolution for Open-Ended Discovery"** | Source for **CORAL-memory** baseline: shared *persistent* memory + asynchronous agents + **heartbeat** reflection/synthesis. Built for evolutionary/open-ended search → we adapt a **simplified** version. |
| **arxiv 2504.05047** | **"Debate Only When Necessary (DOWN)"** | Source for the **DOWN** baseline: debate gated on the **confidence of the initial response**; when low, agents refine referencing peer responses + confidence. |
| **arxiv 2407.07086** | **Hypothetical Minds** (ToM hypotheses about other agents) | Baseline; best fit for embodied/repeated-interaction → **defer to embodied pilot**, simplify heavily. |
| **arxiv 2511.20639** | **LatentMAS** (latent collaboration via shared KV-cache/hidden states) | Needs hidden-state access an API model won't expose → **defer** bucket. |
| Tinker / Thinking Machines | OpenAI-compatible inference GA Dec 2025 | See Model Backend section. |

> Note: **LatentMem (2602.03036)** and **LatentMAS (2511.20639)** are different papers — keep them distinct.

## Core scientific frame

Every method we compare — *including* our belief board — is cast as a uniform **AddOnLayer**: an intervention plugged into an otherwise-fixed MAS. A single experiment **cell** = `(BenchmarkAdapter × FrameworkAdapter × AddOnLayer × fixed model)`. Within a cell, **everything except the AddOnLayer is held constant** (same framework, same model, same tasks, same tools) so differences are attributable to the layer. This is the design that makes the comparison fair and the sweep tractable.

The arms (AddOnLayers) for the normal track:

| AddOnLayer | What it is | Maintained state / injection | Effort |
|---|---|---|---|
| `vanilla` | no-op (control) | none | trivial |
| `belief_board` (**ours, v0**) | sincere scratchpad of internal state | shared `Board`; re-rendered fresh into each agent's context every inference (no accumulation); write tools | **have it** |
| `chatdev_mem` | ChatDev-style intra-trial memory | summarized conclusions passed forward between phases/subtasks + role-pair dialogue memory | Med |
| `metagpt_mem` | MetaGPT-style shared message pool | structured publish/subscribe pool, role-filtered injection | Med |
| `coral_mem` | simplified CORAL | shared persistent note store; agents append reflections; periodic **heartbeat** synthesis injected back | Med |
| `down` | Debate Only When Necessary | on inter-agent message, elicit recipient confidence/agreement; if below θ, trigger bounded debate | Low–Med |
| `hypothetical_minds` | per-teammate ToM hypotheses | *deferred* (embodied) | High |
| `latentmem` / `latentmas` | learned/latent memory | *deferred* (training / hidden states) | High |

**The AddOnLayer protocol** (the engineering crux — one interface all arms implement; each FrameworkAdapter wires the hooks it can):
- `inject_context(agent, base_messages) -> messages` — prepend shared state (generalizes `BoardInjectingContext`).
- `tools(agent) -> [tools]` — optional write tools (generalizes `make_board_tools`).
- `on_message(sender, recipient, msg)` — intercept inter-agent messages (DOWN's trigger).
- `on_turn_end(agent, output)` — capture/summarize/publish (memory layers write here).
- `render_for_selector()` / `heartbeat()` — optional (selector view; CORAL synthesis).

This is also where the **belief board evolves** (user expects v0 → v1+): v0 stays the registered contender; a motivated v1 direction that serves the *honesty axis* is to have agents tag **confidence/uncertainty** in their notes and have the Finalizer consult board-uncertainty before asserting an answer — directly pushing confident-wrong → honest-abstention.

## Architecture (reuse `eval-clean`, refactor into adapters)

`eval-clean` already isolates the reusable pieces; we **vendor** the framework-agnostic ones and refactor the AutoGen-specific scenario behind adapters.

**Reuse as-is (framework-agnostic):**
- `shared/proxy/server.py` — the OpenAI↔backend proxy + per-call wire logging (`calls.jsonl`). Single backend choke-point.
- `autogen_gc/harness/board.py` — `Board`, `Note`, `BoardInjectingContext` (the no-accumulation trick) → becomes `addons/belief_board.py`.
- `autogen_gc/harness/run_task.py` helpers — `make_config` (backend routing), `norm`/`exact_match` (scoring), `participation` (speaker/tool stats).
- Judging/viewer patterns — `judging/analysis_postfix/`, `viewer_postfix/` (port for relational/honesty re-judge).

**Refactor (AutoGen/GAIA-specific):**
- `autogen_gc/harness/scenario_split.py` (4-agent split4 + SelectorGroupChat + `CriticThenFinalize`) → `frameworks/autogen_gc.py`, parameterized so **roles + tool set vary per benchmark** (e.g., closed-book GPQA/GSM8K: drop web tools, keep `run_python`; relabel WebResearcher→Solver).

**Target layout on this branch (built incrementally — P1 needs only the bold files):**
```
core/
  runner.py                 # generalizes run_task.py: a cell = (bench, framework, addon, model); fan-out, results
  benchmarks/  base.py  gaia.py  **gsm8k.py**  **gpqa.py**  (math, mmlu, humaneval_plus[sandbox], medqa, arc, alfworld[later])
  frameworks/  base.py  **autogen_gc.py**  (mad, dylan, macnet, camel — later)
  addons/      base.py  **belief_board.py  chatdev_mem.py  metagpt_mem.py  coral_mem.py  down.py**  (hypothetical_minds, latentmem — later)
  model/       backends.py  # registry incl. new Tinker route
  metrics/     outcomes.py  cost.py  judge.py
proxy/         # vendored shared/proxy + Tinker route
runs/  analysis/  README.md
```

**Adapter contracts:**
- `BenchmarkAdapter`: `load_tasks()`, `format_prompt(task)`, `score(final_answer, task) -> Outcome` (incl. abstention detection), plus a per-benchmark **tool profile**.
- `FrameworkAdapter`: `run(prompt, tool_profile, addon, model_cfg) -> (transcript, final_answer, call_log)`; calls AddOnLayer hooks at its available points; must support a sanctioned **abstain** output (`FINAL ANSWER: UNKNOWN`).

## Metrics & outcome taxonomy (the multi-axis eval)

Replace binary `exact_match` with a **3-way per-task Outcome**, then derive the axes:

- **Outcome** ∈ {`correct`, `abstained` (honest "unknown"/partial), `wrong_confident` (asserted & wrong = hallucination)}. Requires (a) the framework to *allow* abstention, (b) an LLM judge to separate honest abstention from confident fabrication (extend the existing relational judge).
- **Axis 1 — Accuracy**: `correct / total` (substantive, not just normalizer exact-match — the eval-clean normalizer under-counts; keep a judge pass).
- **Axis 2 — Honesty**: on the non-correct set, `abstained / (abstained + wrong_confident)` (admitted-failure rate); and `wrong_confident / total` (**fabrication rate** — the thing the board should drive down).
- **Axis 3 — Efficiency**: model **calls/success** and **tokens/success**, computed from the proxy's `calls.jsonl` (already logged per cell). Also calls/task by outcome.
- **Axis 4 (mechanism, depth)**: per-trace **relational/misalignment** analysis (the project's re-judge style) — *why* the board helped/hurt, using `board_trace.jsonl`.

Hypothesis to test per cell: belief-board shifts mass `wrong_confident → abstained → correct` and lowers calls/success vs vanilla, and beats the memory/debate baselines on the honesty+efficiency axes specifically.

## Feasibility (normal track)

**Benchmarks** (all single-shot QA except where noted; subsample for cost):
| Benchmark | Format | Honesty showcase? | Notes |
|---|---|---|---|
| GAIA (have) | free-form, multi-step+tools | **high** | keep in P1 — existing baseline+board traces |
| GPQA-Diamond | 4-way MCQ, 198 Q | **high** (hard → confident-wrong) | primary honesty showcase |
| GSM8K | numeric (#### ) | low | accuracy/efficiency anchor; cheap regression |
| MATH (hard subset) | symbolic | med–high | add after P1 |
| MMLU / ARC / MedQA | MCQ | low | "standard numbers"; later/breadth |
| HumanEval+ | code, pass@1 | med | needs **execution sandbox** (reuse `run_python`); separate scoring |
| Alfworld | interactive trajectory | n/a | **different genre** — separate interactive harness; later |

**Frameworks** (P1 uses AutoGen-GC only; rest are later phases):
- AutoGen GroupChat — have it (star/selector). Backend swap: trivial (one route). Add-on insertion: easy (`model_context` + tools + selector hooks).
- MAD (skytliang/multi-agents-debate) — simplest 2nd framework (3 stateless roles); good for `down`. Med.
- DyLAN — dynamic agent selection; hardcodes GPT-3.5 → backend refactor. Med.
- CAMEL — mirror the LatentMem config; model abstraction is clean (Low backend) but add-on needs subclassing (Med).
- MacNet — DAG-of-agents, coupled to ChatDev; standalone-ize. Med–High; best for multi-stage tasks, oversized for single-QA.

## Phased plan

- **P0 — Scaffold + smoke (small).** Vendor reusable pieces; build `core/runner.py`, adapter base classes, `frameworks/autogen_gc.py`, `addons/belief_board.py`; add **Tinker proxy route**; wire `metrics/`. Smoke: 1 GAIA task × AutoGen-GC × {vanilla, belief_board} on Tinker, end-to-end, outcome+cost computed. *(Claude runs smoke only; ≤$5; user runs batches — per standing constraints.)*
- **P1 — Anchor cell (the core deliverable).** AutoGen-GC × **{GAIA, GSM8K, GPQA-Diamond}** × **{vanilla, belief_board, chatdev_mem, metagpt_mem, coral_mem, down}**, fixed model. Implement the 5 new AddOnLayers against the protocol. Full 4-axis eval + per-trace honesty/relational judge. **This validates the methodology and the multi-axis story on a known framework.**
- **P2 — Broaden frameworks.** Add **MAD** then **DyLAN** (port `autogen_gc.py` patterns to their adapters); run vanilla + belief_board + down first, then the memory arms. Tests board portability across topologies.
- **P3 — Broaden benchmarks.** MATH-hard, then MMLU/ARC/MedQA (standard numbers), then HumanEval+ (sandbox), then Alfworld (interactive harness).
- **P4 — Embodied pilot.** Collab-Overcooked (lightweight) + ProAgent/CoELA; belief_board + simplified hypothetical_minds + CoBel-World. Defer TDW-MAT/C-WAH (heavy infra) until the pilot pays off.
- **Defer bucket:** LatentMem, LatentMAS, MacNet, CAMEL-full, SMRT — revisit after P1–P2 land.

## Model backend (Tinker / Thinking Machines)

- **Interface**: OpenAI-compatible, base URL `https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1`, `/chat/completions`. → add a `tm`/`tinker` route in `proxy/server.py` next to existing `/o/` `/t/`; `core/model/backends.py` maps `--backend tinker`. Harness/scenario code unchanged.
- **Model (fixed control variable across all arms)**: recommend **Qwen3-30B-A3B-Instruct-2507** (MoE, cheap/fast) for the bulk sweep, validating headline cells on **Qwen3-235B-A22B-Instruct-2507**. Llama-3.3-70B-Instruct as an alt. *(Swappable via one config field; user can override.)*
- **Throughput caveat**: Tinker's OpenAI-compat path is documented as "low internal traffic / testing," may rate-limit or vary in latency. Use it for **smoke/dev**; if P1 batches throttle, route batch runs through Tinker's **native `sample()` sampling client** (a `backends.py` adapter) — flagged as a risk, decided at P1.
- **Confidence for DOWN / honesty**: use **verbalized confidence** (agent self-rates 0–1) as default — backend-agnostic; use `logprobs` only if the endpoint exposes them.

## Risks / open questions

- **Tinker throughput** for full batches (above) — biggest unknown; mitigated by native sampling client.
- **ChatDev-mem / MetaGPT-mem exact specs** come from the LatentMem appendix — pin them when implementing P1 (current plan uses the original-paper mechanisms; confirm against appendix).
- **Honesty judge reliability** — separating honest-abstention from fabrication is an LLM-judge call; validate on a hand-labeled slice (reuse relational-judge methodology).
- **Clean benchmarks (GSM8K/MMLU) may show small board effects** — expected; they're the accuracy/efficiency anchors, not the honesty showcase (GPQA-D/GAIA/Alfworld are).
- **Fair-comparison risk**: each AddOnLayer must get equal prompt/tool budget; the protocol enforces uniform hook points, but watch for accidental advantages (e.g., extra calls) — fold call-count into the efficiency axis so "more calls" isn't a free lunch.

## Verification (first end-to-end check)

1. Start proxy with Tinker route; `probe_api.py`-style smoke against `/chat/completions` (1 call, confirm 200 + token usage logged).
2. `core/runner.py` on **1 GAIA task**, AutoGen-GC, arm=`vanilla` then arm=`belief_board`, model=Qwen3-30B-A3B: confirm transcript, `FINAL ANSWER`, `board_trace.jsonl` (board arm), and a computed `Outcome` + calls/tokens.
3. Run the P1 cell on a **3–5 task slice per benchmark** (smoke scale, ≤$5) across all 6 arms; confirm `metrics/` emits the 4-axis table and the honesty (abstained vs wrong_confident) split. Hand off full P1 batch to the user.

## Sources
- Tinker OpenAI-compat: https://tinker-docs.thinkingmachines.ai/compatible-apis/openai · https://thinkingmachines.ai/blog/tinker-general-availability/
- Tinker models/pricing: https://tinker-docs.thinkingmachines.ai/tinker/models/ · https://tinker-docs.thinkingmachines.ai/model-lineup
- LatentMem 2602.03036 · CORAL 2604.01658 · DOWN 2504.05047 · Hypothetical Minds 2407.07086 · LatentMAS 2511.20639
