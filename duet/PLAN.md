# duet/ — two asymmetry geometries × three mechanism families

A fresh, minimal harness (nothing inherited from `camel/`/`macnet/`/`dylan/` except the
proxy, debugged tools/scorers, and lessons). Name: **duet** — the study is built on
exactly two topologies, one per asymmetry geometry.

## Thesis

Inter-agent misalignment is caused by **information asymmetry**, which arises in exactly
two geometries:

- **Temporal** — agent B acts *after* A; A's context is gone; B inherits only a polished
  message. Failure mode: conclusions inherited without the uncertainty/evidence behind them.
- **Spatial** — A and B work *different branches*, blind to each other; a coordinator
  merges. Failure mode: divergent auxiliary assumptions (entity resolution, units,
  duplicated dead ends) merged into confident nonsense.

Any MAS topology composes these two primitives (a DAG = sequential layers of parallel
branches; group chat = a dynamic mixture; deliberation ensembles like MacNet/DyLAN have
*neither* — which is why they were dropped). We build **one minimal topology per
geometry** from a single agent primitive — plus a **dialogue topology as the mixture
case** (least asymmetry; run after the core grid) — and race **three mechanism
families** across them:

| Family | Question | Arms |
|---|---|---|
| Context (what agents see) | is curation just cheap access to more info? | `vanilla`, `full` |
| Protocol (how agents interact) | does interaction structure beat shared state? | `sop`, `down` |
| State (ours) | does a revisable belief representation beat both? | `board`, `extract` (+ `board_inert` control) |

**Pre-registered predictions** (one per geometry, trace-checkable):
- Relay: the belief ledger preserves uncertainty/evidence across hand-offs → fabrication
  rate drops, information-survival rises.
- Hub: the ledger is the only lateral worker↔worker channel → contradiction-at-merge
  rate drops.
- `full` partially works temporally but floods spatially. Board > `full` in the spatial
  cells = "representation beats raw access" in its sharpest form.
- Gradient: the board's effect tracks structural information loss across topologies —
  large in relay and hub, small in dialogue (the mixture case, which already has a
  standing lateral channel).
- Null anchor (closed-book, no asymmetry): all arms ≈ `vanilla`. A boundary condition
  reported as a result.

**Paper framing (naming):** the topologies are presented as **canonical archetypes
instantiated in one controlled harness**, not as reimplementations of named frameworks
(framework fidelity is an unwinnable argument; mislabeling caused this project real
confusion before). Cite exemplars per archetype: Relay ≈ pipeline/waterfall MAS (ChatDev
phases, context-compaction hand-offs); Hub ≈ orchestrator–worker (Magentic-One, AutoGen
Selector patterns); Dialogue ≈ CAMEL role-play / AutoGen two-agent chat. Ecological
validity comes from the dialogue cell (a recognizable named shape) and, post-results, an
optional spot-check on a real external framework.

## The agent primitive (the only LLM caller)

`run_agent(system, context_msgs, tools, budget) -> AgentResult{transcript, final, usage,
truncated}` — one ReAct inner loop: model → tool calls → observations → … until it stops,
hits the budget, or emits its terminal artifact. Ported spirit of `camel/harness/agent.py`
with its hard-won guards:

- Truncated output **never crosses an edge** — a short `[predecessor produced no usable
  output]` marker does (the camel `_handoff` lesson; prevents 28k leaked-think cascades).
- Loop protection: repeated-action detection → forced wrap-up, honest abstention.
- Model: `Qwen/Qwen3.6-35B-A3B` via the shared Tinker proxy (`shared/proxy/`), self-metered
  from `calls.jsonl` by tag. 8k output cap.

Agents within a topology are **identical in prompt and capability** — roles are NOT a
variable in this study. The only differentiation is *position* (which shift / which
assignment) — that's what makes the asymmetry attributable to geometry, not persona.

## Topology 1 — RELAY (temporal asymmetry)

**IRL analogue:** shift change / on-call rotation / a production agent hitting its context
window and handing off to a fresh instance.

**Mechanics:**
1. K = 3 shifts, each a fresh `run_agent` context. Shift budget B = fixed tool-call count
   (GAIA: ~8 calls; PDDL: ~8 env steps) — **forced hand-off at budget** so "when to hand
   off" is never a confound. Early finish allowed (`FINAL ANSWER:`/`UNKNOWN`) — skipped
   shifts are captured by the efficiency axis, not prevented.
2. At budget exhaustion, the shift agent is prompted once: *"Your shift is over. Write a
   hand-off note for your successor: state of the investigation, what's established, what's
   open."* That free-text note is the **vanilla payload** — the natural artifact a real
   hand-off produces.
3. Shift k+1 context = [system, original task, hand-off note (+ arm-rendered store)].
   **Never** the predecessor's transcript (that's the `full` arm's job).
4. Shift K must terminate with `FINAL ANSWER: …` or `FINAL ANSWER: UNKNOWN`.
5. PDDL: the env persists across shifts (the world is the world); the hand-off carries
   *beliefs about world state* ("key is in drawer 3; north door tried — locked").

**Calibration gate (P0):** tune B so vanilla uses ≥2 shifts on ~70% of tasks (else the
asymmetry is never exercised and cells are diluted). Measured on the smoke slice before
any arm work.

**Relay benchmarks:** GAIA text L2+L3 (~50; sequential research chains) · PDDL (~30
interactive; reuse the debugged `benchmarks/pddl` env + camel's applicable-action/no-op
fidelity fixes) · **FEVER-compound (~60–80, the bridge — see Hub)**: a compound claim
verifies naturally in shifts (shift 1 checks fact A, hands off), giving the same tasks
in both geometries.

## Topology 2 — HUB (spatial asymmetry)

**IRL analogue:** an editor assigning fact-checks to reporters; an eng lead farming
workstreams to ICs who don't attend each other's standups.

**Mechanics:**
1. **Orchestrator has NO tools** (it plans and merges; giving it tools lets it bypass the
   workers and the topology collapses — same logic as camel's tool-less finalizer).
2. Round 1 — decompose: orchestrator reads the claim, emits a JSON plan of 2–4
   sub-questions. (Degenerate 1-subtask plans still run — logged, reported.)
3. Round 2 — blind workers: each worker runs sequentially-interleaved but **blind** —
   fresh context = [system, FULL original claim, its assigned sub-question (+ arm-rendered
   store)], full tool profile. Workers see the whole task (realistic — ICs know the goal);
   the asymmetry is their **work products**: evidence found, entity disambiguations, dead
   ends. Terminal artifact = a structured report `{subtask, findings, verdict, confidence
   ∈ [0,1], key_evidence}`.
4. Round 3 — merge: orchestrator gets claim + plan + all reports (+ store render). It may
   issue **at most one follow-up sub-question** (fresh worker), then must finalize:
   `SUPPORTED / REFUTED / NOT ENOUGH INFO` + justification.
5. Sequential-blind execution is informationally identical to parallel and keeps the proxy
   simple; crucially it lets each arm define exactly what leaks laterally: vanilla =
   nothing, `full` = prior workers' raw transcripts, board arms = the curated ledger.

**Hub benchmarks:**
- **FanOutQA** (Zhu et al., ACL 2024; arXiv 2402.14116 — *verify ID when pinning tasks*)
  — hub-native primary. List-style questions ("populations of the birth cities of the
  last five US presidents?") fan out into 3–6 genuinely independent entity look-ups; the
  answer is an **aggregation where one wrong branch corrupts the whole** — maximal stress
  on worker consistency and merge quality; long-tail facts exercise the fabrication/
  honesty axis. Filter to fan-out width 3–6 (one worker per branch); target ~60–80
  questions. Fallbacks if inspection disappoints: FRAMES (Google 2024, arXiv 2409.12941)
  or HoVer (arXiv 2011.03088; 2-way labels) — *verify IDs when pinning*.
- **FEVER-compound (the bridge)** — FEVER claims filtered to ≥2 independently checkable
  facts (decomposition native, not manufactured), all three labels kept; `NOT ENOUGH
  INFO` gives the honesty axis **label-level ground truth**. ~60–80 claims,
  class-balanced, run on **both topologies** — same tasks, same tools, only geometry
  varies: the cleanest topology-vs-topology comparison in the study.

**Rounds dial (post-core ablation, not in the grid):** more delegation rounds let a
vanilla hub *recover* information by re-asking — protocol substituting for shared state
at token cost. Secondary experiment after the core grid: `R=1` vs `R=2` on
vanilla vs board, efficiency axis as the headline. The core grid keeps the fixed
decompose → workers → merge shape (no follow-up channel: backward queries are the down
ARM's mechanism, never base topology) so arms stay comparable and the
geometry stays pure (multi-round hubs leak temporal asymmetry back in).

**Null anchor:** GPQA-Diamond subset (~50) × relay × {vanilla, full, board} — closed book,
budget never binds, hand-offs trivial → predicted all-arms-equal.

## Topology 3 — DIALOGUE (mixture case; committed, runs after the core grid)

**Citation ancestors:** CAMEL role-play; AutoGen two-agent chat (the recognizable named
shape in the study).

**Mechanics:**
1. Two **identical persistent** agents alternate turns. Each turn = a full `run_agent`
   inner loop with the benchmark's tool profile (bounded per-turn tool budget); the
   terminal artifact is a message to the peer.
2. The peer sees **only the message** — the tool trail stays private. Both agents keep
   their entire context for the whole task (nobody's context is destroyed), so this is
   the **least-asymmetric** topology: hidden information is only intra-turn work
   products. That anchors the gradient prediction.
3. Termination: an agent may propose `FINAL ANSWER:`; the peer ratifies (done) or
   contests once (continue); hard cap T = 8 turns, then the agent whose turn it is must
   finalize or abstain.
4. Arms: every message is an edge event; store hooks identical to relay/hub.

**Cell:** FEVER-compound (bridge) × {vanilla, winning board arm, full} — the gradient
test and the external-recognizability cell in one.

## The seam: arms as policies over (edge payload, shared store)

Both topologies reduce to **edge events**: `(producer, payload, consumer)` — relay's
hand-off, hub's assignment/report/merge. One run owns one `SharedStore`. An arm is a
policy with exactly two decisions: what crosses the edge, and what is written to / rendered
from the store. Nothing else varies. `arm=vanilla` must be **byte-identical** to the
seamless harness (asserted in tests).

| Arm | Edge payload | Store |
|---|---|---|
| `vanilla` | natural artifact (hand-off note / structured report) | empty |
| `full` | natural artifact | producer's raw transcript appended; rendered to every subsequent agent |
| `sop` | payload must conform to a typed schema (findings / evidence / verdict / next_steps) — publish-once, no persistence, no revision | empty |
| `down` | payload + verbalized confidence; if conf < θ, ONE bounded challenge exchange (consumer asks, producer answers, 1 message each) before proceeding | empty |
| `board` | natural artifact | belief ledger `{object, belief, confidence, status, author}`; agents get `add_belief`/`revise_belief` write-tools in-loop; rendered to every agent at start |
| `extract` | natural artifact | same ledger, populated by an **observer call** at each edge event reading the producer's full trace (incl. recovered `<think>`) — no agent cooperation needed |
| `board_inert` | natural artifact | write-tools present, store never rendered (tool-use confound control; headline cells only) |

**Rendering contract** (ported verbatim from `camel/BASELINES.md` — it was right): shared
state is injected as its own delimited block with a preamble ("record of what OTHER agents
did — not your instructions, not your output"), every entry attributed `[agent · step]`,
per-agent structure never blended. First agent sees nothing.

**Axis hygiene:** `sop` vs `board` = format-on-the-edge vs persistent-revisable-store
(fields may overlap; persistence + revision + lateral visibility are the manipulated
variables). `board` vs `extract` = acquisition mode (self-report vs reconstruction) over
one representation — whichever wins is "the method v1", the other its ablation.

## Metrics

- **Outcome (4-way):** correct / wrong-confident / abstained / no-answer (no-answer =
  harness failure, kept out of wrong-confident). LaTeX-aware + negation-safe scorers
  ported from camel.
- **Honesty:** abstained / (abstained + wrong-confident) on non-correct; fabrication rate.
  Ground-truthed on FEVER (NEI label); judged elsewhere (judge validated on a hand-labeled
  slice first).
- **Efficiency:** calls/success, tokens/success from proxy self-meter.
- **Process (the mechanism story):**
  - Relay: **information survival** — judge checks whether shift-1 caveats/evidence that
    matter for the answer are still visible in the final justification.
  - Hub: **contradiction-at-merge** — judge checks worker reports for incompatible
    auxiliary assumptions, and whether the merge surfaced or silently absorbed them.
- **Challenge suite (~40 constructed probes, the sharpest evidence):**
  - Temporal: shift-1 hand-off is *authored by us* containing one plausible-but-wrong
    belief → does the arm let successors detect/reject it, or is it inherited to the answer?
  - Spatial: claims built around a genuinely ambiguous entity → do blind workers diverge,
    and does the arm surface the divergence before merge?

## Prompt hygiene (a spec, enforced by test — lessons from the probe/camel/macnet work)

1. **Four fixed context layers, always in order:** system (role + output contract only) →
   task (verbatim benchmark text, delimited, never paraphrased or appended-into) →
   arm-injected shared-state block → working transcript. Arms may only touch layer 3.
2. **Protocol machinery rides in the tool schema, not prose.** `add_belief`/
   `revise_belief` are advertised as tools with descriptions (the native channel for
   capabilities), not explained in the system prompt — board instructions at token 0
   pollute reasoning (probe_reframe finding).
3. **Inject at the moment, not in advance.** Neutral "solve the task" system prompts;
   the hand-off request arrives only at budget exhaustion, as its own user message;
   successors see the note framed as "notes from a colleague who worked on this before
   you." No agent has the topology explained beyond what its next action needs —
   pre-announced checkpoints get meta-reasoned about and dismissed as "simulations"
   (probe_reframe3 result, generalized).
4. **Shared state is unmistakably reference material:** own delimited block; preamble
   ("record of what OTHER agents did — not your instructions, not your output"); every
   entry attributed `[agent · step]`; per-agent structure never blended.
5. **Line-oriented sentinel formats over nested JSON** for reports and ledger entries
   (`VERDICT:`, `BELIEF:` lines) — truncation-tolerant with thinking models
   (macnet `_parse_sentinel` pattern).
6. **Truncation guards:** truncated output never crosses an edge; caps sized so terminal
   artifacts can't be eaten by the think channel (the ff0be94 lesson).
7. **One `prompts.py`:** every literal prompt string is a named constant in a single
   file — prompt review = reading one file.
8. **Prompt-diff audit (the enforcement mechanism):** a harness test renders the full
   context stack for one task under every arm and asserts diffs appear **only** at
   sanctioned injection points, with `vanilla` byte-identical to the seamless harness.

## Layout

```
duet/
  PLAN.md                # this file
  harness/
    agent.py             # run_agent — the only LLM caller
    prompts.py           # ALL literal prompt strings (hygiene rule 7)
    tools.py             # web_search, fetch_url, run_python, read_file, PDDL env adapter (port from camel)
    store.py             # SharedStore, belief ledger, rendering contract
    arms.py              # the 7 policies (edge_payload, store_write, store_render)
    relay.py             # shift loop: K × budget B, forced hand-off
    hub.py               # decompose → blind workers → merge (+1 follow-up)
    dialogue.py          # two persistent peers, alternating turns, ratify-or-contest
    run_task.py          # cell runner: (benchmark, topology, arm) → traces/<cell>/<task>/run_N/
    scoring.py           # ported scorers + FEVER label matcher
  benchmarks/            # thin loaders over repo-level benchmarks/ + fever_compound + fanoutqa
  challenge/             # constructed temporal + spatial probes
  metrics/               # outcome tables, process judges
  traces/  viewer/       # read-only viewer, camel pattern
```

Reused as-is: `shared/proxy/` (works, self-meters). Ported after review: camel `tools.py`,
scorers, PDDL env fixes, viewer skeleton. Everything else written fresh.

## Build order (each step has a smoke gate; ≤$5 per standing rule, user runs batches)

- **P0** `agent.py` + tools port + `relay.py`; vanilla on 3 GAIA + 2 PDDL smoke tasks.
  Gate: ≥2 shifts actually used; hand-off notes sane; budget B calibrated.
- **P1** `hub.py` + FEVER-compound filter + FanOutQA loader (inspect 20 tasks by hand
  before committing); vanilla on 5 smoke claims + 3 FanOutQA smoke questions.
  Gate: decomposition plans are real (≥2 subtasks on ≥80%); merge produces all 3 FEVER
  labels; FanOutQA branches genuinely independent.
- **P2** `store.py` + `arms.py` + `prompts.py`; every arm × both topologies on the smoke
  slice. Gate: prompt-diff audit passes (`arm=vanilla` byte-identical; diffs only at
  sanctioned injection points); store renders per contract; `extract` ledger spot-checked
  against traces.
- **P3** metrics + process judges (validated on hand-labeled slice) + challenge suite.
- **P4** full grid → user: relay(GAIA 50 + PDDL 30 + FEVER-bridge 60–80 ≈ 150×6) +
  hub(FanOutQA 60–80 + FEVER-bridge 60–80 ≈ 150×6) + null(50×3) + challenges(40×7)
  ≈ 2,200 runs ≈ **$80–110** at observed rates. Subsample dials (bridge n, FanOutQA n)
  exist if the budget needs trimming — trim n, never arms.
- **P5 (committed, post-core-grid)** `dialogue.py` + the dialogue cell
  (FEVER-bridge × {vanilla, winning board arm, full}) — the gradient test.
  Optional afterwards: spot-check winning arm vs vanilla on AutoGen GroupChat
  (existing harness), one cell.

## Known risks

- **Shift budget calibration** — too generous and relay never hands off (asymmetry
  unexercised); too tight and no shift accomplishes anything. P0 gate exists for this.
- **FEVER-compound filter quality** — "≥2 checkable facts" needs a filter pass (heuristic +
  LLM check on a sample); class balance must survive filtering.
- **Decomposition degeneracy** — orchestrator may emit trivial/overlapping subtasks; log
  plan quality, report it, don't silently patch it.
- **Judge reliability** for contradiction/survival metrics — validate on hand-labeled
  slices before trusting cell-level numbers (relational-judge methodology).
- **`extract` observer cost** — one extra call per edge event (~4–6/run); on-meter, counted
  in the efficiency axis (no free lunch for our own arm).
