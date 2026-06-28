# Memory / coordination baselines for the CAMEL pipeline

Status: design doc. Only `vanilla` is built today; everything else is planned.

## Scope & ground rules

- **Intra-trial only.** Cross-trial / cross-task memory (a store that persists and is
  retrieved across tasks) is **out of scope**. Every arm here operates *within a single
  task*.
- **Everything is shared.** Each arm is a single global structure that all 4 agents
  read from and write to — not a per-agent scratchpad. This is the property the study
  cares about (it's the same property our belief board has), which is exactly why these
  are the right baselines.
- **Controlled comparison.** A run holds the pipeline fixed (same 4 agents
  `actor_1 → actor_2 → critic → finalizer`, same edges, same order) and swaps *only* the
  `AddOn`. Any arm that would change the **topology** is rejected as a confound (see
  MetaGPT-M below).
- **Where it bites.** The compaction / forgetting / retrieval arms only diverge from
  `vanilla` when the shared log is **long**. On closed-book **MATH / GPQA-D** each agent
  does ~1 ReAct round (~4 entries total) → these arms ≈ `vanilla`. They only do real work
  on **GAIA** (long, tool-heavy trajectories). Report this rather than hide it.

## Shared definitions

**Entry** = one ReAct round of one agent: `(t, agent, action, observation)`.
- `action` = the assistant message's visible content for that round + the tool name/args
  it called (the stripped `<think>` trace is *not* captured).
- `observation` = that round's tool output(s); `""` if no tool was called.
- `t` = a monotonic index across the **whole task** (all 4 agents share one counter).
- Parsed from `AgentResult.transcript`: skip `system`/`user`; each `assistant` message =
  one entry, the following `tool` message(s) = its observation. (One round can fire
  several tool calls → bundle into one entry, or split per-call for finer retrieval.)
- This mirrors GMemory's `move_memory_state(action, observation)`, sourced from our
  transcript instead of an environment.

**"Full log"** = a downstream agent sees the *entire observable trace* of every agent
that ran before it (every action + tool observation + final answer) — strictly more than
`vanilla`, which passes only each agent's polished `.final` across the edge. The
increment `full` adds over `vanilla` is precisely the intermediate tool observations and
step actions. An agent reads the shared state **once**, via `inject_context`, before its
own loop; its own rounds publish at `on_turn_end`, so the *next* agent sees them.

**The seam** (`harness/addons.py`): `inject_context(role, messages)` = the read-out
(prepend shared state before an agent's loop); `on_turn_end(role, result)` = capture /
commit. Register each arm in `get_addon`.

**Integration mode** — two kinds:
- *Augment* (default for the working-memory arms): keep the existing edge hand-offs; the
  AddOn layers shared state on top (its value-add = the inner tool observations the edges
  drop).
- *Replace* (MetaGPT-M only): the AddOn changes *what crosses the edges*; the hardcoded
  edge content is swapped for structured artifacts. Topology and order unchanged.

## Provenance & faithfulness note (read before citing)

These names come from the **G-Memory** paper/repo (`bingreeky/GMemory`, arXiv 2506.07398).
The repo forces every non-ChatDev baseline through one **cross-trial** template (embed a
finished, labeled task → retrieve similar past tasks). That template is **unfaithful to
the original papers** — most starkly **MetaGPT**, whose real memory is an *intra-trial*
shared message pool, not cross-task retrieval. So our arms are **intra-trial
reconstructions anchored to the original papers**, not ports of the repo's classes. Label
them honestly in any writeup.

## Baseline catalog

| Arm | Axis / what varies | Selection / render | Faithfulness | Mode | Bites on |
|---|---|---|---|---|---|
| `vanilla` | — (control) | only upstream `.final` crosses edges | our control | — | — |
| `full` | quantity (all) | dump every entry verbatim | = GMemory base readout | augment | GAIA |
| `memorybank` | quantity (recency) | drop entries past Ebbinghaus decay | intra-trial forgetting | augment | GAIA |
| `generative` | salience | top-k by recency × importance × relevance | Park et al. retrieval fn | augment | GAIA |
| `chatdev` | quantity (compress) | recent verbatim + LLM summary of the rest | ChatDev-style compaction | augment | GAIA |
| `metagpt-M` | message format | typed role artifacts over fixed edges | MetaGPT SOP factor only | replace | all |
| `voyager` (blurb) | promotion | shared library of short useful blurbs | CORAL-notes / Voyager-flavored | augment | GAIA |

### `vanilla` — control (built)
Current behaviour. No shared memory; only each agent's polished `.final` crosses the
edges. The baseline every arm is measured against.

### `full` — whole shared log
The shared global log of all entries; `inject_context` dumps it verbatim to each agent.
= GMemory's `Empty`/base intra-trial read-out. Cheap; ≈ `vanilla` on short trajectories.

### `memorybank` — recency forgetting
Each entry carries timestamp `t`; keep entries with `exp(-(t_now - t)/5) ≥ 0.3`
(≈ last ~6), drop the rest. Recency-only. No LLM, free. (MemoryBank's original Ebbinghaus
curve is cross-session; we apply it intra-trial as a read-out policy.)

### `generative` — importance × recency × relevance retrieval
Score each entry and inject the **top-k**; the read-out is **role-aware** (the critic
retrieves entries relevant to "verify B", the finalizer to "decide"):
- recency — exponential decay over `t` (Park et al. impl: 0.995^Δ),
- importance — LLM rates the entry 1–10 (one call per new entry),
- relevance — embedding cosine to the current agent's query.
Equally weighted, each min-max normalized. **Cost caveat:** importance = 1 LLM call/entry;
relevance needs embeddings (**off the proxy token meter**). Approximate relevance with
lexical overlap to stay on-meter and LLM-free. (Exact decay constant not re-confirmed
against the PDF; from the paper's described retrieval function.)

### `chatdev` — periodic LLM compaction
Keep recent entries verbatim; once the shared log exceeds a **token budget**, replace the
older portion with an LLM summary (ChatDev's `summary` prompt, run through our proxy so
tokens stay on-meter). The original "every 10th step" trigger is tuned to 30-step env
loops; rescaled to a token budget so it fires on GAIA, never on closed-book.

### `metagpt-M` — structured-protocol (NOT memory)
**Different axis.** MetaGPT's real mechanism is a shared pub/sub message pool — but
adopting that would re-express (or change) our topology, which is a confound. So we keep
**only the SOP factor that is orthogonal to topology**: each role emits a **structured,
typed artifact** (`actors → {answer, evidence, assumptions}`, `critic → {verdict,
wrong_claims, corrected_value}`) that flows along the **existing edges**, replacing the
free-text hand-off. Same 4 nodes, same order; the only manipulated variable is message
*format*. This is a communication-protocol baseline, not shared memory — mostly a
prompt/protocol change, registered through the seam for uniformity.

### `voyager` (blurb) — shared skill/note library
A flat library of short NL **blurbs** (useful learnings, procedures, "where to look"
pointers). When an agent finds something useful it appends a blurb (`on_turn_end`); each
agent loads the library wholesale at turn start (`inject_context`). Optional
**execution-gate** (commit a blurb only when the producing tool/`run_python` round
succeeded — Voyager's actual self-verification) makes it Voyager-flavored; without it,
it's CORAL's `notes/` tier flattened.
- **Honest naming:** this is *not* real Voyager (which is executable code, execution-
  verified, top-k retrieved, and **cross-trial**). It's a shared note library.
- **Watch redundancy with the belief board.** Keep axes sharp: this is *append-only,
  flat, passive*; the belief board is *revisable*. If it collapses to "board minus
  revision," treat it as an **ablation of the board**, not a separate baseline.
- Verifier-last caveat: a critic-gated version is useless here (the critic is agent #3
  and the finalizer has no tools), which is why the gate, if used, is **execution**, not
  the critic. Reach is mainly within an agent's own long loop + the actor_1→actor_2 hop.

## Comparand (our method, not a baseline)
**`belief_board`** — free-form, **revisable** shared notes. Positioned against `metagpt-M`
(structured/publish-once vs free-form/revisable) and against `voyager`-blurb (revisable vs
append-only). This is what the baselines exist to beat.

## To-be-done — Track B: active, tool-mediated memory

`full / memorybank / generative / chatdev / voyager-blurb` are all **passive injected**
memory (the AddOn pushes context in via `inject_context`). The next two are a **different
paradigm**: memory is an **external addressable store** the agent *pulls* from via
**tools**, and must be advertised in the agent's prompt. This needs a second seam
(memory tools in `TOOL_PROFILES` + a backend + prompt changes + read access for the
otherwise tool-less finalizer) — a real subsystem, deliberately staged after Track A.
**Do not fold these into `voyager`** (crossing the passive/active boundary); they should
share infrastructure **with each other** as two access policies over one memory-as-
environment seam.

### CORAL (arXiv 2604.01658) — *to be done*
"CORAL: Towards Autonomous Multi-Agent Evolution for Open-Ended Discovery." Shared
persistent memory is a **filesystem with symlinks** into each agent's workspace, in three
tiers: `attempts/` (solutions + evaluations), `notes/` (observations/reflections),
`skills/` (reusable procedures/code). Access is **navigation/query via a git-like CLI**
(`coral log/show/notes/skills/eval`) + `bash`. Likely a **port of our existing mini-CORAL**
(M0–M7 on another branch), not a from-scratch build.

### DeLM (arXiv 2606.10662) — *to be done*
"Decentralized Multi-Agent Systems with Shared Context" (DeLM). **Three-resolution**
shared context with **selective unfolding**: compact gist `(ℓ,G)` (global view) →
`UNFOLD` to reference-grounded summary `ℒ[ℓ]` → `DEEP_UNFOLD` to raw `ℛ[ℓ]`, so detail
cost scales with need. Writes are **verification-gated**: compress `r→S→G`, check each
bullet against its evidence span, atomically commit.

**Track-B caveat:** both papers' MAS (CORAL's long-running git evolution; DeLM's parallel
queue-claiming) are very different from our 4-agent line, and much of their value lives in
*their* topology. Held to our fixed pipeline we isolate just the **memory representation +
access pattern** — the correct controlled variable, but expect a smaller effect than in
the papers, and the same GAIA-skew (near-empty store ≈ `vanilla` on closed-book).
