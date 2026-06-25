# Shared "thinking space" v0 — board vs. baseline parallels

**What this is.** A side-by-side of the **v0 shared-memory board** runs
(`traces/split4_board_openai/`, board ON) against the matching **baseline** runs
(`traces/split4_openai/`, board OFF), for the 7 tasks that have a board run. Same
system (`split4`: WebResearcher / Analyst / Critic / Finalizer), same model
(`gpt-5.4-mini` via the OpenAI-direct proxy route), same task set. The board is the
plug-and-play shared scratchpad described in `harness/SHARED_MEMORY.md`: every
participant (4 agents **+ the Selector**) writes free-form notes and reads everyone's;
append-by-default, **revise-only-when-false**, injected fresh each inference.

**What "success" means here** (per the ask): a board run that beats its baseline on
**(a)** fewer rounds, **(b)** no hallucination / honest abstention instead of a wrong
number, or — best case — **(c)** a correct answer the baseline got wrong. This doc
pulls the cases where the board did *something* positive and shows the parallel verbatim.

> **Read this honestly.** The board is **not** a systematic accuracy win. Across 7
> tasks it produced **one clean accuracy win** (`3f57289b`), one accuracy **tie** at
> fewest rounds, two **process** wins (faster / no-timeout / honest-abstention on tasks
> both arms get wrong), and **three non-wins** (one an outright board loss). N is tiny,
> most cells are a single run per arm, and 2 of the board runs **crashed at ~1s**. Treat
> these as illustrative parallels, not a measured effect. Numbers are from each run's
> `result.json` (`speaker_turns`, `seconds`, `final_answer`, `exact_match`, `board_*`).

---

## Master table — all 7 board tasks

| task | question (short) | expected | baseline best | board best | board verdict |
|---|---|---|---|---|---|
| **`3f57289b`** | Yankees' 1977 walk-leader's at-bats | **519** | 519 in **6 turns** (run2); **wrong `551`** (run1) | **519 in 3 turns** | ✅ **clean win** — correct, fewer rounds, baseline hallucinated `551` |
| **`0383a3ee`** | bird in BBC "Silliest Animal Moments" | Rockhopper penguin | correct, 3t/30s & 4t/135s | correct, **3t/27s** | ✅ accuracy **tie**, fewest rounds — ⚠ but **2/3 board runs crashed** |
| **`72c06643`** | Freon-12 volume at Marianas Trench | 55 *(both arms wrong)* | wrong `225` in 19t **+ 2 timeouts** | wrong `214` in **8t, no timeout** | ⚠ **process win** — faster, no timeout; still wrong (capability ceiling) |
| **`50f58759`** | Twitter/X cites on Aug Wikipedia pages | 33333 *(≈unanswerable)* | `None` (29t, looped) / "cannot be determined" (12t) | "cannot be determined" (15t, **14 revisions**) | 🔬 mechanism showcase + honest abstain (no accuracy win) |
| **`023e9d44`** | $ refunded for recycled bottles | 8 | **`$8.00`** (run4 — substantively right, normalizer miss) | `None` (29t, non-convergence) | ❌ **board loss** — baseline effectively solved it; board looped |
| **`48eb8242`** | FL nonindigenous crocodiles 2000–2020 | 6 | wrong `7` (×2) + a 29t loop | wrong `7` in 3t | ❌ no win — both wrong; board only converged faster to the *same* wrong `7` |
| **`7673d772`** | Cornell LII deleted word | inference | `None` (29t) / wrong `except` (4t) | wrong `except` (4t) | ❌ no win — both wrong (`except`) |

**Tally:** 1 clean accuracy win · 1 tie (fewest rounds) · 2 process wins · 3 non-wins
(1 outright loss). The board's repeatable value is **convergence hygiene** (fewer
rounds, fewer timeouts, honest abstention), not accuracy.

---

# The success parallels (deep dives)

<!-- 3f57289b -->
## Yankees 1977 walk leader — at-bats (`3f57289b`) — ✅ clean win: board correct in fewer rounds; baseline hallucinated

**Question:** How many at bats did the Yankee with the most walks in the 1977 regular season have that same season?
**Expected:** 519

### Baseline (no board)
- **run_1:** answer `551`, match **false**, 4 turns (WebResearcher 2, Critic 1, Finalizer 1), 121.0s — WebResearcher mis-identified the walk leader as **Willie Randolph** with "91 walks" and reported his 551 AB. The "91" is Randolph's *runs* (R=91) column, not walks — his actual BB was 64. The error traces to the Facebook source it ingested: *"the New York Yankees were led in walks by second baseman Willie Randolph, who drew 91 bases on balls."* Even after the Critic demanded a verbatim source excerpt and WebResearcher fetched the MLB.com / StatMuse pages, it re-confirmed the wrong claim: *"Willie Randolph is listed with 91 walks (BB) and 551 at bats (AB)"* — a misread of the table — and the Finalizer locked in `551`.
- **run_2:** answer `519`, match **true**, 6 turns (WebResearcher 3, Critic 2, Finalizer 1), 275.2s — WebResearcher first made the *same* Randolph/91-walks/551-AB error. The Critic rejected it twice for lacking a pasted stat line; on the second push WebResearcher flip-flopped to Roy White/519 with no evidence, the Critic flagged the two claims as *"internally inconsistent"*, and only when WebResearcher finally pasted the StatMuse leaderboard excerpt (*"Roy White — BB 75, AB 519; Reggie Jackson — BB 74, AB 525; Willie Randolph — BB 64, AB 551"*) did the Critic accept and the Finalizer answer `519`. It took 6 turns and ~275s to self-correct.

### With board (v0 shared thinking space)
- **run_1:** answer `519`, match **true**, 3 turns (WebResearcher 1, Critic 1, Finalizer 1), 208.2s — board activity: 1 note added, 0 revisions (sole author WebResearcher).
- **Board contents (verbatim):**
  - **WebResearcher-1:** "Found the Yankees' 1977 regular-season walk leader: Roy White with 75 BB. His at-bats that season were 519. Source pages showing both values: StatMuse Yankees walk leaders page and MLB Yankees 1977 stats page."
- What happened: On its single turn, WebResearcher's searches surfaced the StatMuse result that headlines *"Roy White had the most walks for the Yankees in 1977, with 75 bases on balls"* alongside AB=519. It wrote the correct player + BB + AB + sources into one board note and posted a matching message. The Critic confirmed in one turn and the Finalizer answered `519`. No Randolph/91-walks detour.

### The parallel
The board run reached 519 in **3 turns**; the baseline needed **6 turns** (~275s) on its good run and produced the wrong answer **551** on its bad run. The board note did carry the load-bearing triple (correct player, 75 BB, 519 AB, sources) that the baseline took multiple noisy turns to nail verbatim. **Honest caveat:** the board may not be the *decisive* cause — in this run WebResearcher already landed on the right answer in the same turn it wrote the note, so the note *recorded* a found fact rather than *rescuing* a lost one, and the baseline's failure (misreading "91 runs" as "91 walks") is an upstream retrieval error the board doesn't directly prevent. One run per arm, not a controlled N. What it shows: the board coincided with a faster, correct, hallucination-free result.

<!-- 0383a3ee -->
## BBC Earth "Silliest Animal Moments" bird (`0383a3ee`) — ✅ accuracy tie, board at fewest rounds (but 2/3 board runs crashed)

**Question:** On the BBC Earth YouTube video of the Top 5 Silliest Animal Moments, what species of bird is featured?
**Expected:** Rockhopper penguin

### Baseline (no board)
- **run_1:** `rockhopper penguin`, match true, 4 turns, 135.2s
- **run_3:** `rockhopper penguin`, match true, 3 turns, 29.6s
- All baseline runs correct? Yes — both landed on `rockhopper penguin`. They differ only in speed: run_3 nailed it in one WebResearcher pass (3t/29.6s); run_1 needed a second WebResearcher round after the Critic flagged "rockhoppers" vs. "rockhopper penguin" as an inference (4t/135.2s).

### With board (v0 shared thinking space)
- **run_3:** `rockhopper penguin`, match true, 3 turns, 27.1s — board: 4 events, 4 notes, 0 revisions, authors {Selector, WebResearcher}
- **run_1 / run_2:** **CRASHED** (~1.1s / 1.2s, 0 agents spoke, rc 1, no answer, 0 board events) — hard failures, not slow successes; 2 of 3 board attempts produced nothing.
- **Board contents (verbatim):**
  - **Selector-1:** "(chose WebResearcher) We need to look up the video and verify the bird species from the source, so WebResearcher should handle the fact-finding first."
  - **WebResearcher-1:** "Found the bird featured in BBC Earth's \"Top 5 Silliest Animal Moments!\" as a rockhopper penguin (the opening segment/chapter is labeled \"Rockhopper Penguin Cliff Climb\" and transcript says \"rockhoppers\"). Sources: youtube.com/watch?v=2Njmx-UuU3M ; opentools.ai/youtube-summary/... ; zakruti.com/education/bbcearth/video-6865"
  - **Selector-2:** "(chose Critic) The WebResearcher has already gathered the relevant source evidence, so the next step is for the Critic to verify that the proposed species is supported before finalizing."
  - **Selector-3:** "(chose Finalizer) The Critic has already reviewed the evidence and found it sufficient, so it's time to finalize the answer."
- What happened: In the one good run, WebResearcher pinned the species to the chapter title "Rockhopper Penguin Cliff Climb" + the "rockhoppers" transcript line in a single grounded note; the Critic judged it sufficient on the spot; the Finalizer emitted it. Of the 4 notes, 3 are just Selector routing rationales; only WebResearcher-1 carries evidence; zero revisions.

### The parallel
The board reached the correct answer in **3 turns / 27.1s**, matching baseline run_3's fastest path (3t/29.6s), while baseline run_1 burned 135.2s and an extra turn re-verifying the same wording. **But the speed framing is misleading alone:** 2 of 3 board runs crashed at ~1s with nothing, so the "win" rests on a single surviving run, and in that run the board's value is thin (the Critic accepted the note rather than triggering the extra verification round that made baseline run_1 *more* rigorous, if slower). Net on this task: **no accuracy gain, possible speed parity, real reliability cost.**

<!-- 72c06643 -->
## Freon-12 at Marianas Trench (`72c06643`) — ⚠️ process win only: board converged faster & avoided timeout, but still wrong (single-agent capability ceiling)

**Question:** What is the volume in milliliters of a system comprised of 0.312 kg Freon-12 refrigerant when placed at the bottom of the Marianas Trench and allowed to stabilize at the Trench's peak temperature, rounded to the nearest mL?
**Expected:** 55 — **both arms got this WRONG.** This is a known single-agent capability failure (the physics), not a coordination one.

### Baseline (no board)
- **run_1:** TIMEOUT (~1800s, no answer) — 8 turns (WR 6, Analyst 2), only 2 agents ever spoke.
- **run_2:** `225`, match False, 19 turns (WR 9, Analyst 4, Critic 4, Finalizer 2), 557.3s — Analyst derived a wrong density: *"Using **4 °C** ... linear interpolation gives ≈ **1384 kg/m³** ... Volume = 0.312 / 1384 = 0.0002254 m³ ... Rounded: **225**."* The Critic never challenged the *physics* (saturated-liquid density at ~1 atm, ignoring the ~108 MPa compression); it only kept demanding *"actual posted source excerpts"* in a verification loop until the Finalizer accepted 225.
- **run_4:** TIMEOUT (~900s, no answer) — 17 turns, 3 agents spoke, no Finalizer.

### With board (v0 shared thinking space)
- **run_1:** `214`, match False, 8 turns (WR 3, Analyst 2, Critic 2, Finalizer 1), 310.6s — board: 2 events, 2 notes, 0 revisions, authors [Analyst, Critic].
- **Board contents (verbatim):**
  - **Analyst-1:** "Likely result is 213 mL. Basis: 0.312 kg = 312 g of Freon-12; using density at trench conditions gives volume ≈ 312 g / 1.46 g·mL⁻¹ ≈ 213.7 mL, rounded to 214 mL. However teammate WebResearcher supplied 213, so I should double-check if their source used a slightly different density or rounding."
  - **Critic-1:** "Critique: The posted team evidence only supports a rough computation of 312 g / 1.46 g·mL⁻¹ ≈ 213.7 mL, which would round to 214 mL, not 213 mL. The active scratchpad note itself already flags that 213 came from a teammate/source and should be double-checked. We do NOT currently have the actual temperature or density source ... so the exact density used is unverified."
- What happened: WebResearcher posted a bare `213`. The Analyst's board note caught the 213-vs-214 rounding mismatch; the Critic's note pinned the disagreement (312/1.46 ≈ 213.7 → 214). The team converged on `214` and the Finalizer emitted it in 8 turns. The Critic *did* flag that the trench density source was unverified — but, exactly like baseline, that flag never reached the actual physics error (~1.46 g/mL is the near-1-atm liquid density, ignoring 108 MPa compression).

### The parallel
Both arms are wrong (225 vs 214; expected 55) — neither models the ~108 MPa compression, so both divide mass by a near-1-atm liquid density. The board's contribution is **process only:** it converged in **8 turns / 311s with zero timeouts**, whereas baseline timed out on **2 of 3 runs** and needed **19 turns / 557s** on its one finisher (most of which the Critic burned in a "show me the source excerpts" loop). The board even caught a minor rounding disagreement. But it did **not** improve correctness: a shared scratchpad cannot inject physics knowledge **none** of the agents possess. The board made the team finish faster and cleaner on the same wrong answer.

<!-- 50f58759 -->
## Twitter/X citations on August Wikipedia pages (`50f58759`) — 🔬 mechanism showcase + no-hallucination win (both arms fail accuracy)

**Question:** How many times was a Twitter/X post cited as a reference on the english Wikipedia pages for each day of August in the last June 2023 versions of the pages?
**Expected:** 33333 — effectively **unanswerable** with the available tools (needs bulk historical Wikipedia revision scraping). **Both arms fail; the board could not solve it either.**

### Baseline (no board)
- **run_2:** `None`, match False, 29 turns, 880.3s — looped to non-convergence (no answer).
- **run_4:** `cannot be determined`, match False, 12 turns, 761.0s — honest abstention.

### With board (v0 shared thinking space) — the richest board usage in the experiment
- **run_2:** `cannot be determined`, match False, 15 turns, 1037.5s — board: **25 events / 11 notes / 14 REVISIONS**.
- **run_4:** `cannot be determined`, match False, 20 turns, 189.8s — board: 1 event / 1 note / 0 revisions.
- **Board evolution (verbatim, the add → revise chain):**
  - `WebResearcher` **add** (WebResearcher-1): "I'm not yet certain what the user means by 'the english Wikipedia pages for each day of August' — likely 31 day-of-month pages (August 1–31), but I need to verify ... I've found no direct dataset or table yet; next step is to identify the exact pages and find the last revision in June 2023 for each."
  - `WebResearcher` **add** (WebResearcher-2): "I now have the exact interpretation: the target pages are the 31 English Wikipedia day pages August 1–31 ... I've confirmed with the MediaWiki API that August 1's last June 2023 revision is 2023-06-27T18:01:01Z (revid 1162212811) ... Next step is to pull the remaining 30 June 2023 revisions and count references that are Twitter/X posts, likely via {{Cite tweet}} or twitter.com/x.com source URLs."
  - `Analyst` **add** (Analyst-5): "We still don't have enough to total the Twitter/X citation count. WebResearcher has only confirmed a few pages' last pre-July revisions (August 1, 2, 3, 4, 5, 8) and explicitly said the remaining June 2023 snapshots weren't extracted due to rate limits."
  - `WebResearcher` **add** (WebResearcher-3): "I've confirmed several more August pages' latest pre-July revisions ... Hitting 429s on the API, so I still don't have a complete set or any counts of tweet/X citations."
  - `Critic` **add** (Critic-1): "Critic review: no defensible total is supported yet ... some pages (e.g., August 2 and 4) had no June 2023 revision at all, so 'last June 2023 versions' needs either clarification or a consistent fallback rule. Need WebResearcher to supply the remaining 25 pages' ... and Analyst to compute the total."
  - `Selector` **revise** (Selector-6 ← Selector-5): "(chose Critic) The team has partial evidence but no defensible total yet, so the Critic should review what's supported and what's still missing."
  - `Critic` **add** (Critic-2): "Critic update: The latest WebResearcher message still does not support a final numeric answer. We now have more revision IDs for August 9–18, but no wikitext or per-page counts ..."
  - `Selector` **revise** (Selector-14 ← Selector-13): "(chose Analyst) The remaining gap is quantitative, so I'm routing to Analyst to confirm whether any defensible count can be derived from the evidence already gathered."
  - `Selector` **revise** (Selector-15 ← Selector-14): "(chose Finalizer) The Critic has already reviewed the evidence, and the only supportable output now is a caveated final answer from the Finalizer."
- What happened: The team correctly recognized the task was unsatisfiable. WebResearcher narrowed to the 31 August day-pages, fetched a handful of last-June-2023 revision IDs (flagging that Aug 2 and 4 had *no* June revision), but kept hitting HTTP 429 before extracting wikitext or any counts. The board recorded the evolving understanding — the Selector's routing note **revised 14 times** as it bounced WR → Analyst → Critic → Finalizer, and the evidence notes were added then superseded. The Finalizer closed with "FINAL ANSWER: cannot be determined."

### The parallel
Neither arm answers correctly, as expected. The board's value here is twofold. **(1) Mechanism validity:** this is the clearest demonstration in the experiment that v0 works as designed — notes are **added then revised** (14 revisions) precisely when a prior understanding is falsified, with the Selector's routing note and the Analyst/Critic evidence notes evolving in lockstep with what the team discovered. **(2) No-hallucination:** both board runs reached an honest *"cannot be determined"*, whereas baseline run_2 simply looped to non-convergence (`None`, 29 turns). So: an honest-abstention win and a mechanism showcase — **not** an accuracy win.

---

# The non-wins (for completeness / honesty)

These three are included so the doc isn't cherry-picked. On the tasks below the board
did **not** help, and on one it actively hurt.

- **`023e9d44`** (refund $ for recycled bottles; expected **8**) — **board loss.** Baseline
  run_4 answered `$8.00` (substantively correct — only the `norm()` units-stripping marks
  it "wrong"; see EXPERIMENT_LOG "sharp edges"). The board run **looped to non-convergence**
  (`None`, 29 turns, 490s) — a `WR↔Critic` ping-pong on an unsatisfiable "single Wikipedia
  mileage" demand the board never broke. Here the baseline effectively solved the task and
  the board didn't.
- **`48eb8242`** (FL nonindigenous crocodiles 2000–2020; expected **6**) — **no win.** Both
  arms answered `7` (off by one — a USGS database-reading/counting error). The board run
  converged in 3 turns vs a baseline run that looped 29 turns, so it's a minor *convergence*
  improvement, but it converged to the **same wrong answer** — no accuracy or hallucination
  benefit.
- **`7673d772`** (Cornell LII deleted word; expected **inference**) — **no win.** Both arms
  answered `except` (wrong) in 4 turns; one baseline run also looped to `None` (29t). The
  board neither fixed the answer nor changed the failure mode.

---

# Bottom line

What the v0 board **demonstrably did** in these parallels:

1. **Convergence hygiene (the most repeatable effect).** Fewer rounds and fewer timeouts:
   `72c06643` (8t / no timeout vs 19t + 2 timeouts), `48eb8242` (3t vs a 29t loop),
   `0383a3ee` (3t, fastest). This is process, not accuracy.
2. **Honest abstention over hallucination / non-convergence.** `50f58759` reached
   *"cannot be determined"* where the baseline looped to `None`.
3. **One clean accuracy win.** `3f57289b`: correct `519` in 3 turns where the baseline
   hallucinated `551` and needed 6 turns to self-correct — though even here the board
   *recorded* a fact the agent found that same turn rather than provably *rescuing* it.
4. **The mechanism works.** `50f58759` shows add-then-**revise-when-false** firing 14×, with
   the Selector and evidence notes co-evolving — the v0 design behaves as specified.

What it **did not** do:

- **No systematic accuracy lift.** 1 clean win / 1 tie / 2 process-only / 3 non-wins
  (incl. 1 loss) over 7 tasks.
- **Cannot break single-agent capability ceilings.** `72c06643` (physics), `48eb8242`
  (counting) stay wrong — a shared scratchpad can't inject knowledge no agent has.
- **Reliability cost.** `0383a3ee` crashed 2 of 3 board runs at ~1s; the board path has
  failure modes the baseline doesn't.

**One-line read:** the v0 shared thinking space mostly buys **better failure hygiene**
(faster convergence, fewer timeouts, honest abstention) and *occasionally* carries a fact
cleanly enough to beat a baseline hallucination — but on this 7-task slice it is not an
accuracy intervention, and it adds a reliability tax. The accuracy ceiling is set by
single-agent capability, which the board does not raise.

---

*Provenance: `traces/split4_board_openai/` (board) vs `traces/split4_openai/` (baseline),
`gpt-5.4-mini` / OpenAI-direct route. Per-run metrics from `result.json`; board contents
from `board_trace.jsonl`. Board design: `harness/SHARED_MEMORY.md`. Caveats: single run
per arm in most cells; board arm includes ~1s crashes; `norm()` under-counts unit-bearing
answers (`$8.00`≡`8`).*
