# Drafts — closed-book belief board (NOT IMPLEMENTED)

Exploratory probe scripts, kept only to **track what we tried**. None of this is wired into
the harness or the AddOnLayer protocol. Each script is a standalone Tinker API call (reads
`TINKER_API_KEY` from the branch-root `.env`; smoke scale, a handful of calls each).

## The problem these explore

The belief board works naturally on **agentic / tool tasks** (GAIA on AutoGen-GC): real tool
calls give natural pauses where an agent can stop and write a note about its in-progress state.
**Closed-book reasoning** (GSM8K / MATH / MCQ) has no such pauses — it's one continuous
`<think>` stream. Qwen3.6 also *always* thinks inline and we can't turn it off
(see `tinker-backend-facts`). So: when/how does an agent post a *live* note mid-reasoning,
without (a) derailing or truncating the trace, and (b) just re-solving the problem from scratch?

## The tries, in order

| # | Script | Idea | Result |
|---|--------|------|--------|
| 1 | `probe_notes.py` | Prompt the model to interleave `[NOTE]...[/NOTE]` markers *inside* its `<think>` as it reasons. | ❌ Doubled think length → truncation (no answer); notes bunch up late as retrospective labels, not live; meta-reasoning confusion. Honesty capture on an under-specified question *did* work. |
| 2 | `probe_prefix_replay.py` | Generate one clean trace, then replay growing prefixes through the model asking "what's your current belief/confidence?" (an *observer* reconstructs the board). | ❌ Used an invented `BELIEF/CONF` format (wrong — see #3). Middle checkpoints came back empty; the thinking reader re-solved and truncated. ~2× cost. |
| 3 | `probe_prefix_realnotes.py` | Same observer-replay, but driven by the **verbatim eval-clean `add_note`/`revise_note` rules**. | ❌ Note *content* now correct, but the reader **re-solved** (dumped all notes at the first checkpoint) instead of tracking the real frontier. ~4.6× cost. |
| 4 | `probe_completion.py` | **Branch-and-ask.** Raw `/v1/completions` can *continue* a partial `<think>`. Cut the trace mid-thought, append an injected "save a note?" question, let the same model continue. The note is grounded in the actual prior tokens (no re-solving). | ✅ Mechanism works: `/completions` continuation is faithful and self-paced. Phrasing of the injected question was still clunky. |
| 5 | `probe_reframe.py` | Put the note rules in the **system prompt** + a terse mid-trace "/post or /revise?" + tell it "you'll be interrupted at checkpoints." | ❌ Backfired: the model meta-reasoned *about the protocol* inside its trace and dismissed the real checkpoint as a "simulation" to ignore. |
| 6 | `probe_reframe2.py` | Strip the protocol scaffolding; **definitions-only** system prompt + a *directive* "reply with one command." | ⚠️ Command extraction now works, but the trunk is still **polluted** — Qwen3.6 sees the commands defined up top and plans to use them inline; trace ballooned to 29 paras and ran out before emitting `FINAL ANSWER`. |
| 7 | `probe_reframe3.py` | **Neutral** generation system prompt (no board words at all); inject the note rules **at the cut point** instead of at token 0. | ✅ Trunk is clean (zero pollution) and finishes; note is faithful + eval-clean-style. Also **KV-reuse-compatible**: the shared prefix is the neutral one, divergence is at the cut (not the system prompt). |
| 8 | `probe_reframe4.py` | Stress-test **dead-end faithfulness** on a problem the model should struggle with (missing-dollar riddle). | ⚠️ Couldn't test it: the model **one-shots memorized classics** — it knows the answer at paragraph 2 and spends the rest drafting its response. The branch re-elicits the known answer regardless of cut; late cuts get steamrolled into answer-output. |
| 9 | `probe_show.py` | One clean end-to-end demo that prints the original thinking, the cut point, the inserted text, and the output (for eyeballing). | Demo only. Confirms **where you cut matters**: cut mid-work → clean `/post`; cut after it's solved → it just keeps explaining. |

## Where this nets out (as of these drafts)

- **Mechanism (how to extract a note): solved.** Neutral trunk + note rules injected at the cut
  (#7) gives clean, faithful, in-style notes and keeps the KV-reuse path open. Production-efficient
  version would use Tinker's native `sample()` (KV fork) instead of stateless `/completions`.
- **Substrate (whether there's anything to extract): open / sobering.** On easy closed-book
  problems a strong model has no genuine in-progress frontier — there's no live "belief" to share,
  and the honesty axis can't even be exercised (the model is never uncertain). This re-confirms the
  **genre split**: the live board's home is agentic / genuinely-hard tasks, not memorized reasoning.
- **Untested:** a genuinely hard problem (hard GPQA/MATH item) where *this* model actually struggles
  — the only place a real frontier (and a faithful dead-end note) could appear.

See memory `tinker-backend-facts` for the validated Tinker capabilities these rely on.
