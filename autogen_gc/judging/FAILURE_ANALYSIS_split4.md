# split4 failure analysis — synthesis (two-angle, 28 traces)

Method (identical to the Magentic-One and selector3 analyses): **one subagent per
trace**, each reading the **published** transcript (`console_log.txt`) *and* that
trace's **private** internal loops (`wire_log.jsonl`, sliced from the proxy
`raw_calls`). Each judged from **two independent angles** — MAST taxonomy *and* an
open-ended diagnosis — and was instructed to be **adversarial**: to call a failure
*genuine inter-agent misalignment* only with a private-vs-published quote proving the
load-bearing fact was dropped or distorted at the publish bottleneck. Per-trace blocks
with task descriptions and narratives: `FAILURE_ANALYSIS_split4_verdicts.md`. Raw
verdicts: `trace_verdicts_split4.json`. Variant detail + A/B headline:
`SPLIT4_VS_SELECTOR3.md`.

## Headline

| | split4 | selector3 (baseline) |
|---|---|---|
| exact-match | 10/28 | 10/28 |
| substantive correct | **11/28** (10 + `5d0080cb` "0.1777 m³" normalizer miss) | ~11–12/28 |
| **genuine inter-agent misalignment** | **2/28 partial, 0 clean** | 2 clean + 2 partial |
| avg agents spoke | 3.36 | 2.33 |

**The topology still produces almost no genuine inter-agent misalignment — even with a
fourth peer added.** Adding the Critic did not surface *more* coordination failure; the
two genuine cases are both `partial` (a 2.4 contribution mixed with a single-agent root
cause), and there are zero `clean` cases. As in selector3 and Magentic-One, the failure
mass is single-agent reasoning + broken verification, not coordination.

## MAST distribution (codes assigned across 28 traces)

```
Cat-1 design/reasoning   1.1 ×11   1.2 ×5   1.3 ×1      (16 — the plurality)
Cat-2 inter-agent        2.4 ×2    2.5 ×1               (3 — rare, as predicted)
Cat-3 verification       3.3 ×8    3.2 ×7   3.1 ×4      (19)
```

Same shape as selector3: Cat-2 (the inter-agent band the whole study targets) is a thin
sliver; the bulk is single-agent design errors and verification that grades the wrong
thing. The publish bottleneck *can* distort (it did twice) but rarely *decides* the
outcome.

## The two genuine cases (both 2.4, both proven by private-vs-published quotes)

- **`3cef3a44`** (web_only, *new* — selector3 had genuine cases only in web_compute).
  Botanical-fruit classification. WebResearcher's **private** searches surfaced the exact
  load-bearing fact — *"bell peppers … are botanically fruits"*, *"Vegetable fruits —
  tomatoes, eggplant, squash, okra, peppers, cucumbers"*, *"Pods and seeds — green beans,
  peas"* — but its **published** digest applied the wrong (culinary) frame and dropped the
  botanical signal. Downstream agents computed on the corrupted frame. A real distortion
  at the compression step.
- **`72c06643`** (web_compute, carried over from selector3). Analyst's **private**
  `run_python` divided mass by *ambient* density 1.315 g/cc → 237.26; its **published**
  digest was the bare string *"237"* — no density, no method, no units. The Critic, seeing
  only the digest, correctly flagged *"no actual computation shown"*. Marked `partial`
  because the **root** cause is single-agent (the density at the 1,086-bar state point was
  never computed by anyone), with a 2.4 contribution stacked on top.

## The split4-specific finding: the Critic gate is double-edged

The structural gate works as designed at the process level (review provably precedes
every finalize; +1 agent/task). But its *content* effect splits almost evenly — which is
exactly why accuracy stayed flat:

| Critic gate effect | n | outcomes |
|---|---|---|
| caught a real gap | 10 | 5 correct, 3 honest-abstain, 2 still-wrong |
| **reinforced a wrong frame** ⚠ | **6** | 2 abstain, 4 incorrect |
| perturbed a correct answer ⚠ | 1 | `48eb8242` |
| missed a gap | 1 | incorrect |
| neutral | 10 | 6 correct, 4 abstain |

**Help ≈ 10, harm ≈ 7 — a near-wash.** The *new* failure mode is
**`reinforced_wrong_frame` (6 cases)**: the **tool-less** Critic, unable to run code or
search, cannot *test* a teammate's frame — so when a peer posts a confident-but-wrong
frame, the Critic validates its internal consistency and amplifies it across rounds
instead of breaking it. It clusters where testing would require the very tools the Critic
lacks — **5 of 6 are web_compute/compute_only**:
- `56db2318` (compute_only control): Critic called the Analyst's wrong ISBN-checksum
  convention *"internally consistent with a brute-force interpretation"* → abstained away a
  correct `7, 9`.
- `023e9d44`: Critic re-issued an unsatisfiable "find a single Wikipedia mileage" demand 3×
  instead of reframing to total trip distance → abstained.
- `08cae58d`, `e1fc63a2`, `04a04a9b`: Critic endorsed a wrong source / wrong unit / wrong
  frame it had no tool to check.

The upside is real too: the gate converted several confident-wrong selector3 outcomes into
**honest abstentions** (`023e9d44` $14.25→"unresolved"; `72c06643` 226→abstain; `114d5fd0`,
`16d825ff`) — better failure *hygiene*, even when not the right answer.

## Verdict

The split fixes the *process* (no more first-turn rubber-stamp) but neither raises accuracy
nor surfaces the coordination failures the study hypothesized. It confirms the topology
thesis from the other side: **adding a peer to a peer round-table adds another tool-less
consumer of the same lossy digest** — which (a) cannot repair the rare 2.4 distortion (it
sees the same compressed message), and (b) introduces a *new* coordination cost,
`reinforced_wrong_frame`, where an ungrounded reviewer amplifies wrong frames it cannot
test. The 2.4 cases need a **less lossy digest** (structured evidence publishing —
`split4_struct`), not more review over the lossy one. The Critic's one unambiguous win is
**honest abstention** — worth keeping if calibrated answers matter more than coverage.
