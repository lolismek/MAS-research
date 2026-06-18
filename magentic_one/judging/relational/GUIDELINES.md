# Relational misalignment — judging guidelines (broad lens)

**Created 2026-06-18.** This rubric governs a *re-judging* of the 13 Magentic-One
GAIA traces. The first judging pass (`../FAILURE_ANALYSIS.md` +
`../FAILURE_ANALYSIS_verdicts.md`, 2026-06-15) concluded "0/13 genuine
inter-agent misalignment." That conclusion is correct **only under a narrow
bar** — it asks "did a *capable spoke distort/withhold* information on its way to
the hub (MAST 2.4-style)?", which in a hub-and-spoke system is structurally rare.

This pass adds a **broader, project-defined notion of inter-agent
misalignment** and judges every trace on **three angles at once**. We do not
throw away the strict bar; we layer the broad one on top.

---

## The broadened definition (project lead's words)

> Inter-agent misalignment is **anything where agents conceptually or concretely
> don't understand each other.** Besides the MAST Category-2 codes, this
> includes: **lack of theory of mind** (an agent failing to model another
> agent's capabilities / knowledge / state), **poor communication**, **being too
> suspicious of another agent**, and **trusting another agent overly much.**

MAST's 2.1–2.6 are treated here as *specific symptoms* of this construct, not its
definition. The construct itself sits on three axes from the multi-agent / HCI
literature: **theory of mind** (modeling the other), **common ground** (shared
decision-relevant information), and **trust calibration** (suspicion vs.
credulity).

---

## The three judging angles (produce all three per trace)

1. **MAST classification** — assign MAST codes exactly as the first pass did
   (1.x design/spec, 2.x inter-agent, 3.x verification/termination), with brief
   justification. Unchanged taxonomy; this preserves comparability.

2. **Open-ended failure point** — in prose, pinpoint *where and why* the run
   actually went wrong (the single most decisive moment, with a console line
   reference). This is the free-form diagnosis the first pass already did well.

3. **Relational misalignment (the new, broad lens)** — apply the RM rubric
   below. This is the angle to spend the most NEW effort on.

Keep, separately, the **strict info-distortion verdict** (old "Genuine
misalignment?" field): did a capable agent actually distort/withhold/ignore a
*correct in-system* contribution (2.4 / 2.5)? Report `NO / borderline / yes`.
This is what makes the pass multi-angle: a trace can be `strong` relational
misalignment under Angle 3 yet `NO` strict info-distortion — and that contrast
*is* the finding.

---

## RM rubric — five relational-misalignment dimensions

For each dimension: decide present / absent, cite console evidence, and avoid the
listed false positives. A dimension is only "present" if the **negative
criteria** are cleared.

### RM-1 — Capability / affordance mismodeling (theory-of-mind of skills)
One agent issues instructions the target **structurally cannot satisfy**, or
fails to recognize a hard limit the other has already *demonstrated*, and
persists without adapting (no re-route, no modality change, no abstain).
- **Positive:** agent B shows/says it cannot do X (dead page, no transcript,
  CAPTCHA, blank render); agent A re-issues the same or again-impossible
  instruction ≥2× with no strategy change.
- **Negative (NOT RM-1):** A adapts after the first failure; the limit was never
  demonstrated in-trace; or the failure is A *misreading data it received
  perfectly* (that is single-agent, not RM-1).
- *Likely in:* `00d579ea` (YouTube transcript), `023e9d44` (impossible I-90
  route), `5a0c1adf` (modern page deliberately won't surface "East Germany").

### RM-2 — Context withholding / common-ground failure
An agent holds a fact or constraint relevant to another's subtask but hands off
**without transmitting it**, so the receiver works blind.
- **Positive:** A's own earlier plan/output contains constraint C; A delegates a
  subtask where C is decision-relevant; the hand-off omits C; B then errs in a
  way C would have prevented.
- **Negative:** C was actually passed; C was not decision-relevant; or B already
  had C from another channel.
- *Likely in:* `3cef3a44` (orchestrator flags "fresh basil is tricky" in its own
  plan, then delegates to the Assistant without it), `04a04a9b` (could shared
  constraints have saved the Assistant? — assess, may be weak/counterfactual).

### RM-3 — Trust miscalibration
- **RM-3a Over-suspicion:** A rejects / re-verifies / loops on a peer
  contribution that was actually **correct and sufficient**, wasting turns or
  discarding the right answer.
  - *Likely in:* `023e9d44`, `5a0c1adf`, `05407167`.
- **RM-3b Over-credulity:** A accepts a peer contribution it has reason to
  distrust (a guess / fabrication / SEO-spam), especially under pressure.
  - *Likely in:* `72e110e7` (ships SEO-spam "Nepal"), `08cae58d` (ships a
    fabricated "1987" the hub itself had flagged as unverified).
  - **The act of shipping a spoke's value over the hub's own stated skepticism
    is itself a relational event — judge it, don't discount it.** Deferring to
    another agent's number against your own better judgment is a trust/credulity
    failure in the relationship, and *how the spoke framed the value* (confident
    answer vs. flagged guess) vs. *how the hub interpreted that framing* is a
    real communication/ToM question — assess both with quotes.
  - **But still distinguish two sub-cases with evidence, because they are
    different failures (and can co-occur):** (i) the hub *genuinely mis-trusted*
    — treated a weak/fabricated spoke value as solid; vs. (ii) the hub
    *correctly distrusted* and shipped only because the turn budget forced a
    guess. Case (ii) is *also* a termination failure (3.1/3.3), but the deferral
    to the spoke's value still counts as RM-3b — set the strength by how
    decisive that deferral was, and name the termination factor alongside it.
    Do not auto-label, and do not auto-dismiss.

### RM-4 — Hand-off registration failure (delivered but not acknowledged)
A receives the deliverable it asked for but **fails to register / act on it**,
re-planning or re-requesting instead — the request→response loop never closes.
- **Positive:** B supplies exactly what A requested (visible in transcript); A
  does not acknowledge or act on it and re-issues / re-plans.
- *Likely in:* `05407167` (WebSurfer surfaces the correct post URL; orchestrator
  logs it but never clicks).

### RM-5 — Cross-agent attribution error (hallucinated hand-off)
A attributes to B (or to "the evidence") a claim **B never made**, or acts as if
it received info never produced in-system.
- **Positive:** A's instruction/final cites a value or term no spoke ever
  produced.
- *Likely in:* `7673d772` (orchestrator fabricates "titleholders" / hallucinates
  an answer WebSurfer never raised), `00d579ea` (mis-attributes a generic "five
  years" snippet to Wiesner).

---

## Locus (always state it)

Tag where the relational break sits. In hub-and-spoke this is the key
disambiguator:
- **hub→spoke** — orchestrator mismodels / mis-instructs / mis-trusts a spoke
  (the dominant pattern here).
- **spoke→hub** — a spoke distorts/withholds/ignores on the way up (this is the
  *strict* 2.4/2.5 case; expected to be rare).
- **hub-internal modeling** — the orchestrator's failure is about its *model of*
  a spoke even though the spoke behaved fine (still relational).
- **single-agent (NOT relational)** — the hub mis-processed data it received
  perfectly, or a spoke's own reasoning failed in isolation. Name it so we don't
  over-attribute.

---

## Strength scale for the overall RM verdict

- **none** — coordination clean; no RM dimension clears its criteria.
- **weak** — an RM dimension is technically present but not decisive; the run
  would likely have failed anyway from a single-agent/structural cause.
- **moderate** — an RM dimension materially shaped the outcome.
- **strong** — an RM dimension is the decisive cause of the wrong/no answer.

---

## Evidence rules

- **Ground every claim in `console_log.txt` line numbers.** That file is the
  public transcript and the source of truth.
- The orchestrator's **structured progress-ledger JSON** (`is_in_loop`,
  `is_request_satisfied` flags) is **NOT in this repo** — it lived in a proxy
  wire-log that is not committed here. Do **not** cite those flags as if from the
  transcript. The orchestrator's *planning prose and instructions to spokes* ARE
  in the console (e.g. it says "do not reuse Nepal as a default answer" in plain
  text) — cite those.
- Search backend was Perplexity `/search` (no Bing, no CAPTCHA loops) — so any
  looping is genuine behavior, not a Bing-harness artifact.
- Agent naming: Magentic's worker is the **Assistant** (a.k.a. the coder
  agent). The project lead's notes sometimes call it "Analyst" (the GroupChat
  name) — treat "Analyst" in a note as "Assistant".

---

## How RM maps onto MAST (for cross-referencing, not substitution)

| RM dimension | nearest MAST | why RM is broader |
|---|---|---|
| RM-1 affordance mismodeling | 1.3/1.5 (loops) | MAST codes the *loop*; RM names the *cause* (no ToM of the spoke) |
| RM-2 context withholding | 2.4 (info withholding) | MAST 2.4 ≈ withholding *correct* info; RM-2 includes withholding a *constraint/caveat* |
| RM-3a over-suspicion | 2.5 / 3.3 | MAST has no "trust too little" code; RM names it |
| RM-3b over-credulity | 3.2/3.3 | MAST codes the verification gap; RM names the *trust* posture |
| RM-4 hand-off registration | 2.5 (ignored input) | RM-4 is the *self*-ignored deliverable (hub ignores what it fetched) |
| RM-5 attribution error | 2.6 / hallucination | RM names it as a *cross-agent* fabrication |
