# AutoGen SelectorGroupChat — experiment log & current state

**Read this first.** This branch (`magentic-tom`) accumulated a lot of exploratory
work. This file is the authoritative record of *what was tried, what is current, and
what is superseded*, so future readers (human or agent) don't mistake a dead end for
the live system. For the architecture rationale see `README.md`; **for what is
actually true right now, this file wins over `README.md` where they disagree.**

---

## TL;DR current state (2026-06)

- **Live system = the `split4` variant** (`scenario_split.py`): a 4-agent
  SelectorGroupChat — **WebResearcher, Analyst, Critic, Finalizer**. The Critic
  reviews and is structurally barred from finalizing; only the Finalizer emits
  `FINAL ANSWER:`, and only after a Critic review (the `CriticThenFinalize`
  termination).
- **Superseded = the `selector3` variant** (`scenario_template.py`): the original
  3-agent design (WebResearcher / Analyst / **Verifier**, where the Verifier both
  reviews *and* finalizes). Kept runnable for contrast, **not** the current system.
  The top diagram in `README.md` still describes this older design.
- **Two model backends, same model** (`gpt-5.4-mini` via the proxy at `:8744`):
  - `--backend pplx` → proxy `/t/` route → Perplexity → **no reasoning summaries**.
  - `--backend openai` → proxy `/o/` route → OpenAI-direct → **reasoning summaries
    captured** (the only batch with private pre-action reasoning; see analyses).
- **Run it:**
  `conda run -n autogen_gc python reproduction/autogen_gc/run_task.py --all --variant split4 --backend openai --parallel 6`
  (proxy must be up; results → `reproduction/runs/autogen_gc/split4_openai/<uid8>/run_*`).
- **Two committed trace analyses + viewers** (see "Analyses" below): `analysis_openai`
  / `viewer_openai` (PRE stall-fix) and `analysis_postfix` / `viewer_postfix` (POST
  stall-fix). They analyze *different* batches of the same 28 tasks — don't conflate.

---

## The journey (chronological, with the dead ends labeled)

1. **Magentic-One Bing trap (prior branch work).** The Magentic-One reproduction's
   WebSurfer got stuck in a Bing-scrape loop — a *harness artifact*, not misalignment.
   Fixed with a de-Bing monkeypatch, later a real search-API backend
   (`reproduction/magentic/_debing/`). This motivated a tool-based (not browser) web
   path for the second system.

2. **AutoGen built as the second baseline** (peer round-table, to contrast
   Magentic-One's star). Started as `selector3` (3 agents, Verifier finalizes).

3. **`split4` introduced** — split the Verifier into a **Critic** (review-only, cannot
   finalize) + **Finalizer** (finalize-only), to force a real adversarial review gate.
   This is the current system.

4. **OpenAI-direct backend added** (`/o/` route) specifically to capture **reasoning
   summaries** (Perplexity hides them at any effort). This is what makes the
   reasoning-vs-published analysis possible.

5. **PROBLEM: the OpenAI/reasoning batch looped badly** — far worse than Perplexity.
   Investigated; the proximate cause was NOT the key, NOT a different model (same
   `gpt-5.4-mini` both sides). Two distinct loop modes were found:

   - **Mode A — speaker misattribution.** AutoGen serializes a teammate's message as
     `role=user`, so the model reads a peer's "stop here" as the *end user* halting it
     and loops "Understood — I'll stop." **Fix:** `TeamAwareAssistantAgent` relabels
     incoming teammate messages in-body (`[Internal team message from <name> — NOT the
     end user]`) + a `TEAM_NOTE` in every system prompt. (Validated: `0ff53813` went
     900s-blank → ~30s-correct.)

   - **Mode B — structural non-convergence.** The selector re-picks a stuck agent.
     Two sub-shapes: (i) *same-speaker grind* (WR picked 8× in a row); (ii)
     *Finalizer reached but defers forever* on an unsatisfiable Critic demand.
     **Fix:** `allow_repeated_speaker=False` (kills consecutive repeats) + a Finalizer
     **STALL/GIVE-UP clause** (finalize anyway when the same item is reported
     unobtainable ≥2×, messages repeat, or the Critic demands evidence the tools can't
     produce; emit `FINAL ANSWER: cannot be determined` if nothing is defensible).

   Both fixes live in `scenario_split.py` (commits `aa78683`, and the Mode A relabel
   in earlier `c6a4e19`-era work).

6. **Post-fix full batch re-run** (28 tasks, `split4 --backend openai --parallel 6`).
   See results below.

7. **Post-fix re-analysis** (`analysis_postfix` / `viewer_postfix`) — same pipeline as
   the pre-fix one, fresh namespace so the pre-fix analysis stays intact for comparison.

---

## Results: pre-fix vs post-fix (28 tasks, same set)

| metric | PRE-fix batch | POST-fix batch |
|---|---|---|
| correct (scored) | 5 | 13 (15 effective: +2 normalizer artifacts) |
| wrong answer | 3 | 9 |
| no-answer / non-convergence | **19** | **4** |
| failure cause: structural-nonconvergence | 16 | 4 |
| genuine misalignment (strong/moderate/weak/none) | 1 / 1 / 16 / 10 | 0 / 2 / 14 / 12 |

The 4 residual non-convergences are a **selector ping-pong** (`WR ↔ Analyst` or
`WR ↔ Critic`, non-consecutive so `allow_repeated_speaker=False` permits it) where the
selector **never routes to the Finalizer**, so the give-up clause can't fire. This is a
genuine MAS coordination failure (the selector's own routing), deliberately **left
unpatched** — patching it with a deterministic `selector_func` would replace the
emergent coordination we're studying with a scripted guarantee.

---

## Key finding (the load-bearing conclusion)

Once the structural-stall **artifacts** are removed, the residual failures are
**single-agent capability errors, not inter-agent misalignment.** Genuine misalignment
is `none`/`weak` in 26/28; zero `strong`. Deep-dive on `72c06643` (the canonical
ping-pong staller): WebResearcher **had all the information it needed** — its system
prompt told it to post evidence + sources, the full transcript and the Critic's
"unsupported" were in its context on every call, its private evidence persisted, it even
computed the right answer (~54 mL, gold 55) once and discarded it, and it demonstrably
knew it wasn't the finalizer (never wrote `FINAL ANSWER:`). It still published a bare
`225`. The cause was an **unresolved instruction conflict** (the task's "answer as just
an integer" vs the system prompt's "post specific numbers/values + cite URLs") that the
agent decided the wrong way, compounded by plain unreliability — **not** a missing-info,
missing-architecture, or coordination problem. This corroborates the Magentic-One
finding that genuine inter-agent misalignment is largely *absent*; what looks like
miscommunication is usually a weak agent fumbling a task it had everything to solve.

---

## File map (what's authoritative vs intermediate)

- `scenario_split.py` — **the live system** (split4 + both fixes). Authoritative.
- `scenario_template.py` — superseded `selector3` (3-agent). Contrast only.
- `run_task.py` — runner. `--variant {selector3,split4}` × `--backend {pplx,openai}`.
- `analysis_openai/` — PRE-fix per-trace analysis (build_inputs → render_md →
  subagent verdicts). `inputs/` is gitignored (regenerable). `MODE_B_walkthrough_08cae58d.md`
  is an annotated exemplar of the defer-forever loop.
- `analysis_postfix/` — POST-fix re-analysis, same pipeline, fresh namespace.
- `../viewer_openai/` (serve :8012) — PRE-fix viewer. `../viewer_postfix/` (serve :8013)
  — POST-fix viewer. Both: click a message → drawer with the private ReAct loop, each
  round's reasoning summary, tools, and the one published message; click the selector
  chip → its routing reasoning.
- `../proxy/server.py` — OpenAI↔Perplexity proxy. `/t/`=pplx (no reasoning),
  `/o/`=openai (reasoning). `raw_calls.jsonl` keyed by tag `agc_<variant>_<backend>_<uid8>_run<N>`.

## Known sharp edges (so they aren't rediscovered the hard way)
- **Pre-fix `README.md` top diagram = the old 3-agent Verifier design.** Use this log.
- **Parallel runs of the SAME task race on the run-number** (both write `run_N`). A
  real `--all` batch fans across distinct task dirs, so this only bites same-task reruns.
- **`norm()` under-counts correct answers** with units/format (`$8.00`≡`8`,
  `0.1777 m^3`≡`0.1777`, `17 thousand hours`≡`17`). Several "wrong"/"no-answer" are
  scoring artifacts, not model errors.
- **Reasoning summaries only exist on `--backend openai` runs.** Perplexity hides them.
