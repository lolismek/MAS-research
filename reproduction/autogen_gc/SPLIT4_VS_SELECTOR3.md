# split4 vs selector3 — head-to-head (structural review gate)

Both variants share the **entire** harness (tools, proxy, scoring, 28-task set) and
differ only in the verifier topology, so this slice isolates one variable: replacing
the single self-grading **Verifier** (`selector3`) with a **Critic** (reviews,
forbidden to finalize) + **Finalizer** (only sentinel emitter) behind the
`CriticThenFinalize` termination gate (`split4`). See `README.md` → Topology variants.

Both batches: `--all --parallel 4`, 1 try/task. selector3 baseline at
`runs/autogen_gc/<uid8>/`; split4 at `runs/autogen_gc/split4/<uid8>/`.

## Headline

| metric | selector3 | split4 |
|---|---|---|
| exact-match | **10/28** | **10/28** |
| avg agents spoke | 2.33 | **3.36** |
| avg seconds/task | 71 | 150 |
| batch spend | $1.33 | $4.42 |

Accuracy is flat. Everything interesting is underneath it.

## The gate works — at the *process* level

The 28-trace analysis found the single Verifier finalized on its **first turn in
20/28** traces, skipping review entirely (an unenforced prompt, not a bug —
`FAILURE_ANALYSIS.md`). `split4` makes review **structural**: `CriticThenFinalize`
terminates the run only when a Finalizer sentinel follows a Critic message, so a
genuine Critic review provably precedes every finalization. The participation jump
(2.33 → 3.36 agents/task, +1 as designed) confirms the gate fired on every task —
the rubber-stamp is gone.

## 4 flips, net zero

| task | cat | s3 → s4 | mechanism |
|---|---|---|---|
| `f0f46385` | web_compute | ✗ → ✓ | **real win**: review caught a wrong fact (Brunei/Timor-Leste → Indonesia/Myanmar) |
| `5a0c1adf` | web_only | ✗ → ✓ | **artifact win**: the digest-leak parse bug — Finalizer emits a clean `FINAL ANSWER:` instead of a raw `web_search` dump captured as the answer |
| `e29834fd` | web_compute | ✓ → ✗ | extra review rounds perturbed a correct answer (21 → 20) |
| `56db2318` | compute_only | ✓ → ✗ | **key regression** — tool-less Critic reinforced a wrong frame (below) |

## The `56db2318` regression is the real finding

`56db2318` is a **single-agent compute control** (only the Analyst has `run_python`).
selector3 answered correctly (`7, 9`). In split4 the Analyst locked onto a *wrong*
ISBN-checksum convention (left-to-right alternating weights), found "no valid
solution," and the **Critic — which has no tools — validated it**: the trace shows the
Critic repeatedly calling the claim *"internally consistent with a brute-force
interpretation"* and reinforcing the limited conclusion, never challenging the wrong
assumption. It **cannot** challenge it: with no `run_python` it can only reason over
the posted digest, not test an alternative convention. The Finalizer then abstained
("no valid solution"). **The extra reviewer made a correct answer worse.**

## Verdict — sharpens the topology thesis

The Critic split fixes the **process** (no more premature finalize) but **not the
pathology**:

1. **It can't repair MAST 2.4 distortion.** The Critic is another *tool-less consumer
   of the same lossy published digest*. On the genuine distortion cases (`023e9d44`
   $14.25→"unresolved", `72c06643` 226→"can't justify", `0b260a57`) the gate converted
   confident-wrong into honest abstention on some — better failure *hygiene*, but still
   not the right answer, because the load-bearing fact was already dropped at the
   publish bottleneck before the Critic ever saw it.
2. **It introduces a new failure mode.** An ungrounded reviewer can rubber-stamp or
   *reinforce* a wrong frame it has no capability to test (`56db2318`), and extra rounds
   can perturb a correct answer (`e29834fd`).

So adding a peer to a peer topology did not add capability — it added another
digest-bottleneck node and more inter-agent failure surface. This is the inverse of
what Magentic-One's star does (one reasoner sees its own raw work, no peer digest to
distort). The fix for the 2.4 cases is not *more review over the lossy digest* but a
**less lossy digest** (structured evidence publishing) — the `split4_struct` direction.
