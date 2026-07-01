# Context & token-limit management

How the CAMEL harness handles the two ends of a finite context window — output
truncation and input growth — plus how it *classifies* a truncation so a harness
limit never gets scored as a model failure.

All line references are to `camel/harness/agent.py` and `camel/harness/pipeline.py`
unless noted. Constants are env-overridable (the `CAMEL_*` names are shown inline).

---

## 0. The shared constraint

One model, one window: **`MODEL_CTX = 64000`** tokens (`agent.py:29`,
`CAMEL_MODEL_CTX`). **Input and output share that window** — every ReAct step
re-sends the entire growing message list as the prompt and then asks for output on
top. So "token limit" and "context limit" are two ends of the *same* 64K budget;
most of the design is about partitioning it.

One implicit saver underlies everything: the Tinker proxy strips each turn's
`<think>…</think>` trace before returning it (`shared/proxy/server.py:419`,
`_split_think`). Reasoning is **not carried forward** across ReAct steps — only the
visible answer text and tool calls accumulate, not the (often huge) chain-of-thought.
This is why raw tool observations are load-bearing (see §6).

---

## 1. Output truncation — the adaptive output cap

**The failure it fixes.** The proxy defaults every call to
`TINKER_MAX_TOKENS = 8192` (`server.py:94`, forwarded at `:550`). On an always-thinking
model the reasoning trace can consume that whole budget, so hard GPQA/MATH replies were
cut off *mid-derivation, before the `FINAL ANSWER:` line* — the dominant closed-book
failure, and it was being mis-scored as a confident-wrong answer.

**The fix.** `run_agent` sets its own `max_tokens` on every call, sized adaptively
(`_max_tokens_for`, `agent.py:57-59`):

```
max_tokens = clamp( MODEL_CTX − est_prompt_tokens − _CTX_MARGIN,  [2048, MAX_OUTPUT_TOKENS] )
```

with `MAX_OUTPUT_TOKENS = 28000` (`:30`, `CAMEL_MAX_TOKENS`) and
`_CTX_MARGIN = 2048` (`:31`). Consequences:

- The cap is raised far above 8192 (up to 28K) so reasoning + answer fit.
- We never request output that would push `prompt + output` past 64K — as a tool
  history grows, available output room **shrinks automatically** instead of producing
  a hard 400.
- It floors at 2048, so the model always gets *some* room to answer.

`_est_prompt_tokens` (`:45-54`) is a deliberately cheap `chars/4` estimate (no
tokenizer in the env), counting message `content` plus tool-call `arguments`. It is
used only to *reserve headroom*, so an **over-estimate is the safe direction** — we'd
rather ask for slightly less output than overflow. The reactive net in §3 exists
because this estimate can still under-shoot.

---

## 2. Input growth — capping and compacting the ReAct tool history

Only the tool-using benchmark (GAIA) grows its input: the loop re-sends the whole
tool history every step. Two layers bound it.

### 2a. Cap each tool result at the source (`_truncate`, `agent.py:70-72`)

A single fetched page can exceed the whole window, so every tool result is clipped
before it enters the messages, with a visible `…[truncated N chars]` note:

- **`MAX_TOOL_CHARS = 6000`** (`:62`) for web/compute results.
- **`FILE_TOOL_CHARS = 45000`** (`:66`) for `read_file` (`_FILE_TOOLS`, `:67`): the
  attached file *is* the task, so clipping it at the web-page cap would silently drop
  data rows. `read_file` self-limits internally; this larger ceiling just lets its
  output (including its own truncation note) through whole.

### 2b. Lazy, oldest-first compaction (`_bound_context`, `agent.py:86-105`)

Called proactively at the top of every loop step (`:176`). Properties:

- **Lazy with hysteresis.** No-op until the estimated prompt crosses the
  high-watermark `MODEL_CTX − trigger_headroom` = 64000 − 8000 = **56K**. Once
  triggered, it frees down to the low-watermark `MODEL_CTX − target_headroom` =
  64000 − 16000 = **48K**. The 8K gap (`_COMPACT_TRIGGER_HEADROOM = 8000`,
  `_COMPACT_TARGET_HEADROOM = 16000`; `:40-41`, `CAMEL_COMPACT_TRIGGER` /
  `CAMEL_COMPACT_TARGET`) is hysteresis — it stops us re-compacting on every call.
- **Oldest-first, re-fetchable stubs.** It walks tool results in order and replaces
  the *oldest* with a one-line stub
  `"[elided] name(args…) -> N chars elided to free context"` (`_STUB_PREFIX`, `:42`),
  stopping as soon as it is back under the low-watermark. The label comes from
  `_tool_call_index` (`:75-83`), so the agent can still see *what the call was* and
  re-issue it if it still needs that data — eviction, not amnesia.
- **Freshest result always kept full.** `keep_last` (`:96`) never stubs the most
  recent observation — the thing the model is most likely reasoning about right now.
- Already-stubbed results are skipped, so repeated passes don't churn.

---

## 3. Reactive net — when the estimate is wrong (`agent.py:181-195`)

The `chars/4` estimate can under-shoot. If a `create()` call still throws a
context-overflow error (`_is_context_overflow`, `:108-110`, matches
`context` / `exceeds` / `max_tokens` in the message), the loop:

1. **compacts harder** — `_bound_context` with `trigger_headroom=MODEL_CTX` (forces it
   to always act) and `target_headroom=MODEL_CTX // 2` (frees a full half the window,
   to ~32K) (`:186`);
2. **retries once** (`:187-190`);
3. if it still fails, **gives up gracefully**: publishes the best assistant text it
   has and marks `finish="ctx_overflow"` — no crash (`:191-195`).

---

## 4. Cross-agent edge — don't propagate a truncated answer (`pipeline.py:82-91`)

A second-order effect of the higher output cap: an agent could emit a ~28K-token
"answer" that was really **leaked think** — it ran out of budget before closing
`</think>`, so `_split_think` handed back raw reasoning instead of an answer. Dumping
that into the *next* agent's prompt both balloons its context and feeds it untrustworthy
content.

**Fix — `_handoff`**, applied at all three inter-agent edges (`pipeline.py:107,114,124-126`):
if the upstream agent `.truncated`, the edge carries a short marker
(`"[the previous agent ran out of space before producing a usable answer]"`) instead of
its raw `.final`. The downstream agent treats it as "no answer" rather than inheriting
the reasoning dump. (Committed in `b580a35`. Forward-looking: the committed trace set
predates it and was not re-run; realistic impact ≈ 2 tasks.)

---

## 5. Detecting & classifying truncation (so metrics stay honest)

Knowing *why* a loop ended is what keeps a truncation from masquerading as a
hallucination.

- **`finish_reason` captured every step** and mapped to `AgentResult.finish`
  (`agent.py:198,215`): `"length"` (hit the output cap mid-reply), `"step_cap"` (ran
  `MAX_INNER_STEPS = 30` out, `:20`/`:225-228`), `"ctx_overflow"` (reactive path gave
  up), or `"stop"` (clean).
- **`AgentResult.truncated`** (`:146-151`) = `finish in {length, step_cap, ctx_overflow}`
  — the single signal both `_handoff` and the outcome classifier read.
- **`no_answer` outcome.** A truncated pipeline that never produced a parseable answer
  is scored `no_answer`, deliberately kept **out** of `wrong_confident` so a harness
  failure can't be counted as a model hallucination (protects the honesty axis).
- **`committed`** (`pipeline.py:60-66`): `"FINAL ANSWER:" in final OR finish == "stop"`.
  A short reply that *finished cleanly* but slipped the format still counts as a
  committed (possibly wrong) answer — so we don't hide genuine confident-wrong cases.
- **Finalizer forced-format retry** (`pipeline.py:132-138`): if the finalizer rambled
  past the cap and left no `FINAL ANSWER:` line, it gets exactly one constrained retry
  that can only emit that line — recovering an answer present in the reasoning but never
  formatted.

---

## 6. Design rationale — why raw observations are *kept*, not dropped

A natural question: in the ReAct loop, why store the full (truncated) web/tool result
at all? Why not keep only the action plus the model's reaction to it?

Because **the reaction is not a reliable summary of the observation**, and in this
harness the observation is often the *only* persistent record of what a tool returned:

- The model isn't asked to summarize. Its visible output between tool calls is usually
  just the *next action*, often with near-empty `content` — not a digest of the page.
- We **strip `<think>` every turn** (§0). Whatever the model reasoned about the
  observation is gone by the next step. So if we also dropped the raw observation, the
  next step would see "I searched for X" with no idea what came back, and would be forced
  to re-search or hallucinate.

Appending the raw (truncated) observation is also the **canonical, simplest-correct**
pattern — it's what the original ReAct, LangChain tool agents, smolagents, and the plain
OpenAI function-calling loop all do. Dropping it is not standard and would be incorrect
here.

The principled improvement is **not** "drop it" but **"distill then evict"**: have the
model emit a short, *visible* extract of each observation (or run a separate summarizer)
and retain that in place of the raw scrollback. Our `_bound_context` is a crude version
of this — it evicts oldest raw observations down to a re-fetchable pointer, lossy but
recoverable, **without** distilling. The summarize-then-evict upgrade is exactly the seam
the belief-board / working-memory add-on is meant to fill, and is **not yet built**.

---

## 7. Backstops (orthogonal but related to runaway context)

- **Step cap** `MAX_INNER_STEPS = 30` (`agent.py:20`): a runaway tool loop
  self-terminates (`finish="step_cap"`) rather than growing context forever.
- **Per-task USD budget** (`Budget`, `agent.py:113-134`; `BUDGET_USD = 1.0`,
  `run_task.py:46`): charged live from each response's usage; once it crosses the cap it
  latches and the pipeline short-circuits to an honest `UNKNOWN`. Catches the case where
  context games keep *working* but the task is thrashing expensively. Rates:
  prefill `$0.36`/MTok, sample `$0.89`/MTok (`run_task.py:41-42`).

---

## 8. Where each layer fires

- **GPQA / MATH (closed-book, no tools):** input never grows; compaction (§2b) and the
  reactive net (§3) are dormant. The live lever is the **adaptive output cap** (§1),
  which is what recovered these benchmarks from the 8192 truncation.
- **GAIA (tool-using):** everything engages — per-result caps (§2a), lazy compaction
  (§2b), the reactive 400 net (§3), the step cap, and the budget cap. This is the only
  place the 64K *input* wall is a live concern.

---

## 9. Known limitations

- The prompt-size signal is a `chars/4` heuristic, not a real tokenizer — hence the
  reactive net behind the proactive bound.
- Compaction is **eviction**, not summarization: an elided observation is gone
  (re-fetchable via its stub label, but not condensed). Summarize-then-evict (§6) would
  retain more signal per token and is the intended add-on upgrade.
- `_handoff` (§4) is forward-looking: the committed 88.8% trace set predates it and was
  not re-run (realistic impact ≈ 2 tasks).
