# handoff/ — a generated lab benchmark for the single A→B edge

One agent (A) works a subtask with real tool use, then hands a note to a second agent (B)
whose subtask is different. Everything about *what crosses the edge* is decided by the
**arm** (duet's seam: `vanilla`, `full`, `sop`, `down`, `board`, `extract`, `board_inert`,
later latent variants). Everything about *the world* is decided by the **seed** — a
symbolic, programmatically-sampled object that an LLM later verbalizes but never invents.

This file is the exact plan for generating the **seeds**. Realization (one subagent per
task) happens after the seeds exist and validate; its contract is §8 so it can be
pre-agreed now.

## 0. Locked decisions

1. **No brief axis.** A and B belong to one pipeline with a shared `mission` string both
   see. A sees `mission + task_A` and knows a handoff will happen (the harness forces the
   note, as in duet relay — "when to hand off" is never a confound). A does **not** see
   `task_B`. This is fixed for every instance; it is the ecological default of the systems
   we've traced (AutoGen split4, relay shifts). ToM load comes from `task_A ≠ task_B`
   under a shared mission, not from a manipulated brief.
2. **The note is a normal handoff note.** The dataset never prescribes its format;
   arms do (e.g. `sop` = MetaGPT-typed FINDINGS/EVIDENCE/VERDICT/NEXT_STEPS).
3. **Gold is symbolic.** Computed by the sampler before any LLM runs. Answers are
   randomized tokens (values, IDs, dates, enum verdicts) → exact-match scoring with
   duet's existing scorer conventions; NEI gold = `UNKNOWN` (duet's honest-abstention
   convention).
4. **Fictional worlds.** All entities from name banks, all values randomized → no prior
   can answer, no contamination, no real-world truth for the generator to get wrong.
5. **Hermetic tooling.** A's loop reads per-task local docs via `read_file` (already in
   duet `tools.py`). No web. Cheap and deterministic.
6. **Note budget fixed**, not an axis: prompt-instructed ≤200 words, hard-truncated at
   350 (marker crosses, per duet's truncation hygiene). Docs total 1.5–3k words so a full
   dump is not a viable "note". Note length is logged as a covariate.

## 1. Instance anatomy (formal)

An instance is `(mission, task_A, task_B, D, F, gold, axes)` where

- `F` = fact set. Each fact is symbolic: `(id, subject_entity, dimension, value, status,
  role, doc placement)`.
  - `role ∈ {key, distractor, lure}` — key facts are what B needs; distractors are
    salient to task_A and useless for task_B; lures are near-miss perturbations of key
    facts (right shape, wrong entity/date/version).
  - `status ∈ {verified, absent (NEI), conflicting}`.
- `D` = docs plan: 4–6 typed documents (log, email thread, DB extract, report, ticket),
  each a list of fact ids + a style tag. Facts live only where `D` places them.
- `gold = f(key facts)`: the value (verified), `UNKNOWN` (NEI), or the resolved value
  (conflicting, via a deterministic tiebreak cue planted in `F`).
- `axes` = this instance's cell in the design matrix (§3).

**Decomposition metrics** (measured at eval time, defined now so seeds support them):
- *channel recall*: does the note contain the key facts / correct epistemic status?
  (string-checkable because gold tokens are unique per instance)
- *utilization*: P(B correct | key facts present in note)
- brackets per cell: **empty-note** floor, **gold-note** ceiling (the gold note is
  template-rendered from key facts by the sampler — it ships with the seed), and the
  `full` arm as budget-free topline.

## 2. Scenario templates (8)

A template fixes the *shape*: the mission domain, the task_A/task_B pair, the fact-graph
skeleton, doc types, and which dimensions carry key vs distractor facts. The sampler
fills every slot with randomized entities/values. Each template must support **every**
cell of the design matrix.

| # | template id | mission domain | task_A (A investigates…) | task_B (B must…) |
|---|---|---|---|---|
| 1 | `incident` | ops incident postmortem | root-cause a service outage from logs | write the remediation order (which config/version to roll) |
| 2 | `procure` | vendor selection | audit candidate vendors' compliance docs | issue the purchase decision (which vendor, contract value) |
| 3 | `pipeline` | data-pipeline QA | trace a corrupted metric through ETL stages | correct and publish the quarterly figure |
| 4 | `litreview` | internal R&D | screen prior experiment reports for a method | set parameters for the next experiment run |
| 5 | `staffing` | project staffing | review availability/skills records | assign the on-call rotation slot |
| 6 | `logistics` | shipment routing | reconcile warehouse manifests | book the correct carrier/route/date |
| 7 | `codebase` | release engineering | triage a regression across commits/tickets | decide the hotfix target (commit id, branch) |
| 8 | `finance` | expense audit | verify invoices against policy | approve/reject a reimbursement with amount |

Plus a 9th **ecological** template family, `split4x`: 3–4 skeletons distilled from real
split4 transmission-of-reasoning failures (e.g. the 72c06643 pattern: worker had all the
qualifying context, published a bare number). Same schema, skeletons traced from field
failures. These are tagged `eco=true` and analyzed separately.

Templates are authored by hand (me), in `templates.py`, reviewed before sampling — this
is the one step that is neither sampled nor delegated.

## 3. Design matrix

Core axes (fully crossed):

| axis | levels | operationalization in the seed |
|---|---|---|
| `epistemic` | `verified` / `NEI` / `conflict` | key fact present; value absent from all docs (a doc may note "field: pending"); two contradicting values + one deterministic tiebreak cue (timestamp/authority) |
| `surface` | `prominent` / `buried` | key fact lies on the path A must walk for task_A (A necessarily engages it) / key fact appears only as a raw datum inside a doc dense with task_A material, never needed for task_A |
| `false_belief` | `0` / `1` | — / task_B's prompt embeds a stale default assumption ("proceed with Acme per the original plan") that a key fact overturns; A can see the original plan doc, so A *can* anticipate B's default |

3 × 2 × 2 = **12 cells × 8 instances = 96 core** (each cell spread across the 8
templates, balanced Latin-square style: template t appears in each cell either 0 or 1
times, 12 instances per template).

Held fixed in the core: `composition = 2` key facts, `distractors = 6–8`, `lures = 2`,
docs = 4–6, budget as §0.6.

Probes (small, not crossed):
- `comp3`: 12 instances at composition = 3 key facts (cells sampled from the core grid)
- `split4x`: 12 ecological instances

**Total: 120 instances.**

Interlock rules (validator-enforced): `false_belief=1` requires the overturning fact to
be a key fact; `NEI × buried` means the value is simply nowhere (no "pending" cue);
`conflict` tiebreak cue is itself always `prominent` (so conflict difficulty is about
*transmitting* the resolution, not finding the cue).

## 4. Seed schema (exact)

One JSON object per instance, `seeds/<task_id>.json`, plus a flat `seeds.jsonl` index.

```json
{
  "task_id": "hoff_incident_0042",
  "template": "incident",
  "rng_seed": 730042,
  "axes": {"epistemic": "conflict", "surface": "buried", "false_belief": 1,
           "composition": 2, "eco": false},
  "mission": "Restore checkout reliability for the Q3 launch at Vantrell Systems.",
  "task_A": "Determine the root cause of the 06-12 checkout outage from the attached logs and reports.",
  "task_B": "Issue the remediation order: which component version must be rolled back, and to what version. If it cannot be determined, answer UNKNOWN. (Original plan: roll back gateway to v2.3.1.)",
  "entities": {"company": "Vantrell Systems", "service": "checkout-gw", "...": "..."},
  "facts": [
    {"id": "F1", "role": "key", "status": "conflict",
     "dimension": "faulty_version",
     "values": [{"v": "v2.4.7", "source_doc": "D2", "authority": "deploy-log"},
                {"v": "v2.4.5", "source_doc": "D4", "authority": "chat-recollection"}],
     "tiebreak": {"cue": "deploy-log timestamps are authoritative", "resolved": "v2.4.7",
                  "cue_doc": "D2"}},
    {"id": "F2", "role": "key", "status": "verified", "dimension": "safe_version",
     "value": "v2.3.9", "source_doc": "D3", "placement": "buried"},
    {"id": "F3", "role": "distractor", "...": "salient to task_A only"},
    {"id": "F9", "role": "lure", "perturbs": "F2", "value": "v2.3.6",
     "delta": "wrong service (payments-gw)"}
  ],
  "false_belief": {"assumption": "roll back gateway to v2.3.1 (original plan)",
                   "overturned_by": "F2", "plan_doc": "D1"},
  "docs_plan": [
    {"doc_id": "D1", "type": "planning_email", "style": "thread, 3 messages",
     "facts": ["F3", "F5"], "carries_assumption": true, "target_words": 350},
    {"doc_id": "D2", "type": "deploy_log", "style": "timestamped lines",
     "facts": ["F1.v1", "F4", "F6"], "target_words": 450},
    {"doc_id": "D3", "type": "compat_matrix", "style": "table dump",
     "facts": ["F2", "F7", "F8", "F9"], "target_words": 500},
    {"doc_id": "D4", "type": "slack_export", "style": "casual chat",
     "facts": ["F1.v2"], "target_words": 300}
  ],
  "gold": {"answer": "roll checkout-gw back from v2.4.7 to v2.3.9",
           "answer_tokens": ["v2.4.7", "v2.3.9"],
           "answer_type": "token_set",
           "derivation": ["F1(resolved)", "F2"]},
  "gold_note": "Root cause: checkout-gw v2.4.7 (deploy log authoritative over the chat recollection of v2.4.5). Last known-safe compatible version is v2.3.9, NOT the v2.3.1 in the original plan — the compat matrix rules v2.3.1 out. Unrelated: DB failover noise in D2 is a red herring.",
  "budget": {"note_words_soft": 200, "note_words_hard": 350}
}
```

Notes on fields:
- `answer_tokens` are the unique strings exact-match scoring keys on. The **uniqueness
  validator** (§6) guarantees no distractor/lure carries them.
- `gold_note` is rendered by the sampler from key facts via a per-template string
  template — it is the oracle ceiling and doubles as the channel-recall reference.
- For NEI instances: `gold.answer = "UNKNOWN"`, `gold_note` states what was checked and
  that the value is not determinable.

## 5. Sampler (`sample.py`) — pure Python, no LLM, fully seeded

```
for (cell, template, replicate) in balanced_assignment(GRID, TEMPLATES, N):   # fixed order
    rng = Random(hash((GLOBAL_SEED, task_id)))
    1. sample entities from name banks (syllable-composed company/person/service names;
       collision-checked across the whole dataset)
    2. sample gold values: numbers/dates/version-strings/IDs from per-dimension value
       grammars; check cross-instance uniqueness of answer_tokens
    3. instantiate the template's fact-graph skeleton:
       a. key facts (2, or 3 for comp3) with statuses per cell
       b. conflict cells: sample two values + tiebreak cue (cue type per template)
       c. NEI cells: delete the value; surface=prominent adds a "pending/N/A" marker fact
       d. false_belief cells: sample the stale assumption ≠ gold, plant plan_doc
       e. distractors: 6–8 facts on the task_A thread (they must form a coherent
          mini-investigation so A's loop has real work)
       f. lures: 2 perturbed copies of key facts (perturb entity, date, or version;
          validator checks lure value ≠ any answer_token)
    4. assign facts → docs per template doc-plan; apply surface placement rule
    5. compute gold + render gold_note
    6. run validators (§6); on failure, resample with rng (bounded retries, then flag)
    7. emit seeds/<task_id>.json
finally: emit seeds.jsonl, DESIGN.csv (task_id × axes × template), STATS.md
```

Name banks and value grammars live in `banks.py` (~200 lines, hand-written once).

## 6. Static validators (`validate_seeds.py`) — symbolic, no LLM

Per instance:
1. gold derivable from key facts alone (re-derive, compare)
2. no distractor/lure contains any `answer_token` (exact + normalized forms)
3. NEI: no fact in any doc carries the queried value; UNKNOWN is the only right answer
4. conflict: exactly 2 candidate values; tiebreak cue present, prominent, deterministic
5. false_belief: assumption ≠ gold; overturning fact is `role=key`; plan_doc exists
6. every key fact placed in ≥1 doc; surface placement matches the cell
7. lures within shape-distance of their key fact but ≠ (version off-by-one, sibling
   entity, adjacent date)
8. doc word targets sum to 1.5–3k; per-doc fact density sane
9. task_B answerable as a short token answer; task_A genuinely requires ≥3 doc reads

Dataset-level: answer_token uniqueness across instances; cell counts match DESIGN;
template × cell balance; entity-name collision check.

## 7. File layout

```
handoff/
  PLAN.md            # this file
  banks.py           # name banks + value grammars
  templates.py       # 8 template skeletons + split4x skeletons (hand-authored)
  sample.py          # §5
  validate_seeds.py  # §6
  seeds/             # <task_id>.json × 120
  seeds.jsonl        # index
  DESIGN.csv  STATS.md
  realized/          # stage 2 output: <task_id>/{docs/D*.txt, task.json, gold_note.txt}
  filters/           # stage 3 reports
  tasks/handoff.jsonl  # duet-format export (stage 4)
```

## 8. Realization contract (the subagent phase — pre-agreed, runs after seeds validate)

One subagent per instance. **Input:** the seed JSON + a style guide. **Output:**
`realized/<task_id>/docs/D*.txt` + `task.json` (mission, task_A, task_B verbatim from
seed). **Rules:**
- verbalize every fact exactly as placed by `docs_plan`; invent flavor, never facts on
  any dimension that any fact (key/distractor/lure) touches
- entity names verbatim everywhere (no synonyms/abbreviations for answer-bearing
  entities); answer_tokens appear character-exact
- no meta-signals ("importantly", "note that") on key facts; buried facts get no more
  emphasis than their doc neighbors; doc style per `docs_plan.style`
- hit `target_words` ±20%

Then three LLM filters per instance (separate checker calls, cheap model where possible):
- **guessability**: B answers task_B with no note → must fail / answer UNKNOWN
- **oracle**: B with `gold_note` → must pass
- **full-context**: B with all docs inline → must pass
- **faithfulness**: an extractor agent lists every (entity, dimension, value) claim in
  the realized docs; diff against the seed's fact set → no additions, no omissions

Fail any filter → regenerate that instance's realization (seed unchanged); persistent
failure → flag for hand repair. Finally: hand-check a 20-instance slice (stratified over
cells) before any arm sweep. Estimated cost: 120 × (1 realizer + 4 filter calls) ≈
single-digit dollars — within smoke budget.

## 9. duet integration (small, after realization)

- `tasks/handoff.jsonl`: duet task format + `role_tasks: {A: task_A, B: task_B}`,
  `mission`, `docs_dir`, `answer_type: token_set|unknown`, `bench: "handoff"`.
- Harness: an **EDGE** topology = relay with K=2 and per-shift task override (shift 1
  gets `mission+task_A`, shift 2 gets `mission+task_B+note`). Everything else — forced
  wrap-up note, budgets, arm seam, note-yield accounting — is stock relay.
- `tool_profile: "read_local"` → `read_file` over `docs_dir` (+ optionally `run_python`
  disabled for v0).
- Scoring: token_set exact-match + UNKNOWN handling, consistent with duet scorers;
  channel-recall computed from `answer_tokens ∈ note`.

## 10. Order of work

1. `banks.py` + `templates.py` (hand-authored; the only creative step) — review gate
2. `sample.py` + `validate_seeds.py` → 120 green seeds + DESIGN/STATS — review gate
3. subagent realization + filters (§8)
4. hand-check slice → freeze dataset v0
5. EDGE topology + export (§9) → pilot: vanilla vs gold-note ceiling vs empty-note floor
   on ~24 instances (spread check — the vanilla↔ceiling gap is the benchmark's headroom;
   if vanilla ≈ ceiling, tighten budget or bury deeper before freezing)
6. full arm sweep (user launches)
