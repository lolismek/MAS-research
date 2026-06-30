"""AddOnLayer seam for the CAMEL-style pipeline.

Every coordination/memory method (our shared belief board, chatdev/metagpt-style
memory, DOWN, ...) is the SAME interface plugged into an otherwise-fixed pipeline.
A run holds everything constant except the AddOn, so any difference is the layer's.

State flows between agents only across the pipeline's edges (here 3 backbone:
actor_1->actor_2->critic->finalizer, plus 2 skip-edges into the finalizer). No
matter how many edges, the layer needs only two hooks — they fire per agent, so
they cover every inbound edge:

  - inject_context(role, messages) -> messages
        Called inside run_agent BEFORE the inner loop. Prepend shared state
        (the board, retrieved memory, ...) onto this agent's message list.
        This is the "ctx" from the design sketch: for vanilla it returns the
        messages unchanged, so the only thing crossing an edge is the upstream
        agent's polished output.

  - on_turn_end(role, result) -> None
        Called AFTER an agent finishes its inner loop. Capture / summarize /
        publish (a memory layer writes the agent's sincere state here).

vanilla = both hooks are no-ops. belief_board (next) overrides both: inject the
board, and write the agent's note on turn end.
"""
import json
import math
import os
import re


class AddOn:
    """No-op base == the `vanilla` control arm.

    Beyond the two core hooks (`inject_context` / `on_turn_end`), the base exposes
    four ADDITIVE seam extensions, all inert here so `vanilla` is byte-identical to
    the pre-AddOn pipeline. Arms override only what they need:
      - `bind`           : receive the per-task client/model/budget (arms that make
                           their own LLM calls — chatdev summary, generative importance).
      - `system_prompt`  : let an arm swap a role's system prompt (metagpt-M).
      - `extra_tool_specs` / `run_extra_tool` : let an arm add an agent-callable
                           write-tool backed by per-task addon state (voyager).
    """
    name = "vanilla"

    def inject_context(self, role, messages):
        return messages

    def on_turn_end(self, role, result):
        return None

    # --- additive seam extensions (inert in base) ----------------------------
    def bind(self, client, model, budget):
        """Hand the arm the per-task client/model/budget (called once in run_one,
        right after construction). Arms that make their own metered LLM calls use
        these; vanilla and the no-LLM arms ignore them."""
        self.client, self.model, self.budget = client, model, budget

    def system_prompt(self, role, default):
        """Return the system prompt for `role`. Base = the pipeline's default,
        unchanged. metagpt-M overrides to emit structured-artifact prompts."""
        return default

    def extra_tool_specs(self, role):
        """OpenAI tool specs this arm adds to `role`'s profile (base: none).
        voyager advertises `add_skill` here for the actors/critic."""
        return []

    def run_extra_tool(self, name, arguments):
        """Dispatch an addon-owned tool call against this arm's per-task state.
        Returns a string (goes straight into a `tool` message), never raises —
        matching tools.run_tool's recoverable-error contract."""
        return f"ERROR: unknown tool {name!r}."


# =============================================================================
# Track A — passive injected working memory (shared intra-trial log)
# =============================================================================
#
# A single global log, shared by all 4 agents, built from their ReAct transcripts.
# An ENTRY = one ReAct round: (t, label, action, observation), where
#   - t           = a monotonic index across the WHOLE task (all 4 agents share it),
#   - label       = which agent produced it ("actor_1"/"actor_2"/"critic"/"finalizer"),
#   - action      = that round's assistant text + the tool name/args it called,
#   - observation = that round's tool output(s) ("" if it called no tool).
# Each agent CAPTURES its own rounds at on_turn_end and READS the (policy-filtered)
# log at inject_context, rendered per the read-out contract below. Arms differ only
# in `select()` (which entries survive) — the parse + render are shared.

# The read-out contract: the shared log is GLOBAL and crosses agent switches, so it
# must be rendered so the receiving agent never mistakes it for the task, for new
# instructions, or for its own output.
_PREAMBLE = (
    "Below is the shared record of what OTHER agents have already done on this task. "
    "It is reference material — NOT your instructions, NOT the task itself, and NOT "
    "your own prior output. Each entry is tagged with the agent and step that produced "
    "it. Use it to inform your answer.")

# Per-observation cap when rendering an entry: tool observations (fetched pages, file
# dumps) can be huge; the shared log re-sends them to every downstream agent, so cap
# each one to keep the injected block well inside the model context. `full` is still
# "the whole log" — just with each observation bounded.
_OBS_RENDER_CAP = 1500
_ACTION_RENDER_CAP = 800
# An action's conclusion (e.g. the 'FINAL ANSWER:' line) sits at the END, which a
# head-only clip drops — so for action text we ALSO keep the last N chars. Observations
# get no tail: their useful content is at the top; the tail is usually boilerplate.
_ACTION_RENDER_TAIL = 400


def _clip(s, cap, tail=0):
    """Bound rendered text. Default = head-only (keep the first `cap` chars). With
    `tail>0`, keep the first `cap` AND the last `tail` chars, eliding the middle — so an
    agent's answer, which lives at the end of its reasoning, survives the clip."""
    s = (s or "").strip()
    if len(s) <= cap + tail:
        return s
    if tail:
        return s[:cap] + f" …[+{len(s) - cap - tail} chars]… " + s[-tail:]
    return s[:cap] + f" …[+{len(s) - cap} chars]"


class WorkingMemoryAddOn(AddOn):
    """Shared global ReAct log; `full` = inject all of it. Base for the working-memory
    arms — subclasses override only `select()` (and optionally `_annotate()`)."""
    name = "full"
    LABELS = ("actor_1", "actor_2", "critic", "finalizer")   # fixed pipeline order

    def __init__(self):
        # ALL mutable per-task state lives on the instance (one addon per task; tasks
        # run across threads in run_batch). Never class-level.
        self.log = []        # list of entry dicts {t, label, action, observation, ...}
        self._t = 0          # global monotonic entry counter
        self._turn = 0       # how many agents have finished (0=actor_1's turn, ...)

    # ---- labelling -----------------------------------------------------------
    def _label(self):
        # min-clamp: the finalizer RETRY (pipeline.py) fires a 5th hook pair, which
        # would otherwise index past LABELS. It is still the finalizer, so clamp.
        return self.LABELS[min(self._turn, len(self.LABELS) - 1)]

    # ---- capture (shared) ----------------------------------------------------
    def _parse_entries(self, transcript):
        """One entry per assistant message; its observation = the tool message(s) that
        answer its tool_calls (matched by id). Skips system/user — so the injected
        scratchpad (a USER message) is NOT re-ingested as this agent's own rounds."""
        entries = []
        for m in transcript:
            if m.get("role") != "assistant":
                continue
            action = (m.get("content") or "").strip()
            calls = m.get("tool_calls") or []
            if calls:
                descs = []
                for tc in calls:
                    fn = tc.get("function") or {}
                    descs.append(f"{fn.get('name', 'tool')}({(fn.get('arguments') or '')})")
                action = (action + "\n" if action else "") + "calls: " + "; ".join(descs)
                ids = {tc.get("id") for tc in calls}
                obs = "\n".join(mm.get("content") or "" for mm in transcript
                                if mm.get("role") == "tool" and mm.get("tool_call_id") in ids)
            else:
                obs = ""
            if not action and not obs:
                continue
            entries.append({"action": action, "observation": obs.strip()})
        return entries

    def _annotate(self, entry):
        """Hook to enrich an entry at creation time (base: no-op). Generative scores
        `importance` here so the LLM call happens once per entry, not per inject."""
        return None

    def on_turn_end(self, role, result):
        label = self._label()
        assert label.startswith(role), f"label/role desync: {label!r} vs {role!r}"
        for e in self._parse_entries(result.transcript):
            e["t"], e["label"] = self._t, label
            self._annotate(e)
            self.log.append(e)
            self._t += 1
        self._turn += 1

    # ---- read-out (shared) ---------------------------------------------------
    def _query(self, role, messages):
        """Role-aware query string (used by relevance-ranking arms; ignored by full)."""
        if role == "critic":
            return "verify the proposed answer's claims and arithmetic"
        if role == "finalizer":
            return "decide the final answer from the candidates and critique"
        return next((m.get("content") or "" for m in messages if m.get("role") == "user"), "")

    def select(self, role, cur, query):
        """Which entries to inject. Base = the whole log (`full`)."""
        return list(self.log)

    def _render(self, sel, cur):
        """The read-out contract, as ONE message. MUST be role 'user' (never
        'assistant'): the same message goes back through this agent's transcript at
        on_turn_end, and an assistant-role block would be re-ingested as new entries."""
        lines = []
        for e in sel:
            # a compacted summary entry (chatdev) sets a larger cap so it isn't clipped
            action = _clip(e["action"], e.get("action_cap", _ACTION_RENDER_CAP),
                           tail=_ACTION_RENDER_TAIL)
            obs = _clip(e.get("observation"), _OBS_RENDER_CAP)
            arrow = f"\n  → {obs}" if obs else ""
            lines.append(f"[{e['label']} · step {e['t']}] {action}{arrow}")
        body = "\n".join(lines)
        return {"role": "user",
                "content": f"{_PREAMBLE}\n<shared_scratchpad>\n{body}\n</shared_scratchpad>"}

    def inject_context(self, role, messages):
        cur = self._label()
        # `!= cur` drops any entry this agent itself produced — a no-op normally (an
        # agent's entries aren't in the log until on_turn_end), but it stops the
        # retried finalizer from being shown its own first-pass entries.
        sel = [e for e in self.select(role, cur, self._query(role, messages))
               if e["label"] != cur]
        if not sel:                      # actor_1 (empty log) injects nothing
            return messages
        return messages + [self._render(sel, cur)]


def _entry_text(e):
    return e["action"] + (("\n" + e["observation"]) if e.get("observation") else "")


def _tokens(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def _minmax(vals):
    """Normalize a list to [0,1]; all-equal -> all 0.0 (a constant term can't change
    the ranking, so its absolute value is irrelevant)."""
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return [0.0] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


# --- memorybank: recency-only forgetting -------------------------------------
# MemoryBank's Ebbinghaus curve is cross-session in the original; we apply it
# intra-trial as a READ policy: keep an entry while its retention exp(-age/S) >= τ.
_MB_STRENGTH = float(os.environ.get("CAMEL_MEMORYBANK_S", 5.0))
_MB_THRESHOLD = float(os.environ.get("CAMEL_MEMORYBANK_TAU", 0.3))


class MemoryBank(WorkingMemoryAddOn):
    """Forget by recency: drop entries whose retention has decayed below τ
    (≈ keep the last ~6). No LLM, free."""
    name = "memorybank"

    def select(self, role, cur, query):
        return [e for e in self.log
                if math.exp(-(self._t - e["t"]) / _MB_STRENGTH) >= _MB_THRESHOLD]


# --- generative: importance × recency × relevance retrieval ------------------
# Park et al.'s retrieval function: rank by the (min-max normalized) SUM of three
# scores and inject the top-k. recency = exponential decay; importance = an LLM
# rates each entry once, at creation; relevance = lexical overlap with a role-aware
# query (NOT embeddings — those are off the proxy token meter).
_GEN_TOPK = int(os.environ.get("CAMEL_GENERATIVE_TOPK", 6))
_GEN_RECENCY_DECAY = float(os.environ.get("CAMEL_GENERATIVE_DECAY", 0.995))


class Generative(WorkingMemoryAddOn):
    name = "generative"

    def _annotate(self, entry):
        """Score importance ONCE, when the entry is created (not per inject)."""
        entry["importance"] = self._rate_importance(entry)

    def _rate_importance(self, entry):
        """LLM rates the entry 1-10. Metered (charges the per-task budget) and
        budget-gated: if the cap is blown, skip the call and use a neutral 5."""
        budget = getattr(self, "budget", None)
        client = getattr(self, "client", None)
        if client is None or (budget is not None and budget.exceeded):
            return 5
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system",
                           "content": "Rate how important this step is for solving the "
                                      "task, 1 (trivial) to 10 (crucial). Reply with ONLY "
                                      "the integer."},
                          {"role": "user", "content": _entry_text(entry)[:1500]}],
                temperature=0.0, stream=False,
                # generous cap: a thinking model spends output tokens on its <think>
                # trace (proxy strips it) before emitting the number — too small a cap
                # truncates it to empty. It still stops early once the integer is out.
                max_tokens=1024)
            if budget is not None:
                budget.charge(getattr(resp, "usage", None))
            m = re.search(r"\d+", resp.choices[0].message.content or "")
            return min(10, max(1, int(m.group()))) if m else 5
        except Exception:
            return 5

    def select(self, role, cur, query):
        cands = list(self.log)
        if len(cands) <= _GEN_TOPK:
            return cands
        qtok = _tokens(query)
        recency = [_GEN_RECENCY_DECAY ** (self._t - e["t"]) for e in cands]
        importance = [e.get("importance", 5) for e in cands]
        relevance = []
        for e in cands:
            et = _tokens(_entry_text(e))
            inter = len(qtok & et)
            union = len(qtok | et) or 1
            relevance.append(inter / union)          # Jaccard overlap with the query
        score = [a + b + c for a, b, c in
                 zip(_minmax(recency), _minmax(importance), _minmax(relevance))]
        ranked = sorted(range(len(cands)), key=lambda i: score[i], reverse=True)[:_GEN_TOPK]
        # restore chronological order so the injected scratchpad still reads top-to-bottom
        return [cands[i] for i in sorted(ranked)]


# --- chatdev: periodic LLM compaction ----------------------------------------
# Keep the most recent entries verbatim; once the shared log's size exceeds a budget,
# replace the OLDER portion with one LLM summary. ChatDev's original "every 10th step"
# trigger is tuned to 30-step env loops; we rescale to a size budget so it fires on long
# (GAIA) trajectories and never on closed-book. The summary stays CONTAINERIZED BY AGENT
# ([actor_1] …; [actor_2] …) so the receiving agent never loses who-did-what.
_CD_BUDGET_CHARS = int(os.environ.get("CAMEL_CHATDEV_BUDGET", 8000))   # lower it to force compaction
_CD_RECENT = int(os.environ.get("CAMEL_CHATDEV_RECENT", 3))           # entries kept verbatim
_CD_SUMMARY_SYS = (
    "You compress an agent team's shared work log, PRESERVING WHO DID WHAT. Group strictly "
    "by agent and output at most two terse lines per agent, each starting with that agent's "
    "tag, e.g. '[actor_1] computed X; found Y'. NEVER merge multiple agents into one "
    "anonymous paragraph. Keep only facts useful for finishing the task.")


class ChatDev(WorkingMemoryAddOn):
    name = "chatdev"

    def __init__(self):
        super().__init__()
        self._summary_cache = {}      # older-count -> summary text (the log only grows)

    def select(self, role, cur, query):
        log = list(self.log)
        if len(log) <= _CD_RECENT or sum(len(_entry_text(e)) for e in log) <= _CD_BUDGET_CHARS:
            return log                                  # under budget -> no compaction (== full)
        older, recent = log[:-_CD_RECENT], log[-_CD_RECENT:]
        summary = {"t": older[-1]["t"], "label": "summary", "observation": "",
                   "action": self._summarize(older), "action_cap": 4000}
        return [summary] + recent

    def _summarize(self, older):
        key = len(older)                                # cache so it isn't recomputed per inject
        if key not in self._summary_cache:
            self._summary_cache[key] = self._llm_summary(older)
        return self._summary_cache[key]

    def _llm_summary(self, older):
        rendered = "\n".join(f"[{e['label']} · step {e['t']}] {_entry_text(e)[:600]}"
                             for e in older)
        budget = getattr(self, "budget", None)
        client = getattr(self, "client", None)
        if client is None or (budget is not None and budget.exceeded):
            return self._cheap_summary(older)           # budget blown -> free fallback
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": _CD_SUMMARY_SYS},
                          {"role": "user", "content": rendered[:8000]}],
                temperature=0.0, stream=False, max_tokens=2000)
            if budget is not None:
                budget.charge(getattr(resp, "usage", None))
            return (resp.choices[0].message.content or "").strip() or self._cheap_summary(older)
        except Exception:
            return self._cheap_summary(older)

    def _cheap_summary(self, older):
        """No-LLM fallback: per-agent step counts. Preserves who-did-what (not the
        content), so the per-agent containment contract still holds."""
        counts = {}
        for e in older:
            counts[e["label"]] = counts.get(e["label"], 0) + 1
        return ("Earlier steps (elided, summary unavailable): "
                + "; ".join(f"[{k}] {v} step(s)" for k, v in counts.items()))


# =============================================================================
# metagpt-M — structured-protocol baseline (NOT shared memory)
# =============================================================================
#
# MetaGPT's real mechanism is a shared pub/sub message pool, but adopting that would
# re-express our topology (a confound). So we keep ONLY the SOP factor that is
# orthogonal to topology: each role emits a STRUCTURED, TYPED artifact instead of free
# text. The artifact becomes the agent's `.final` and rides the EXISTING edges verbatim
# (pipeline interpolates `.final`), so topology and order are unchanged — the only
# manipulated variable is message FORMAT. This is a communication-protocol arm, not
# memory: `inject_context`/`on_turn_end` stay no-ops (inherited from AddOn).
#
# Honest limitation: prompt-only yields *prompted*-structured artifacts, not *validated*
# typed ones (no parse/repair) — the right choice for a format baseline; hard validation
# would be a new subsystem and a confound.
_MG_ACTOR_SYS = (
    "You are a problem solver on a team that communicates via STRUCTURED ARTIFACTS. Solve "
    "the task, using the available tools when they help. Report your result as EXACTLY these "
    "three labeled fields, each starting on its own line, and write nothing after them:\n"
    "ANSWER: <your final answer>\n"
    "EVIDENCE: <the key facts, computations, or sources that justify the answer>\n"
    "ASSUMPTIONS: <any assumptions or caveats you relied on; write 'none' if none>")

_MG_CRITIC_SYS = (
    "You VERIFY another agent's proposed answer. Do NOT solve the task from scratch. Use the "
    "tools to check the specific claims and arithmetic IN the proposed answer. Report your "
    "verdict as EXACTLY these three labeled fields, each on its own line, nothing after:\n"
    "VERDICT: <agree | disagree>\n"
    "WRONG_CLAIMS: <the specific claim(s) that are wrong, or 'none'>\n"
    "CORRECTED_VALUE: <the correct value if you found an error, or 'none'>")


class MetaGPT(AddOn):
    """SOP factor only: actors/critic emit typed artifacts over the fixed edges. The
    finalizer keeps its default prompt so it still emits the parseable FINAL ANSWER line."""
    name = "metagpt-M"

    def system_prompt(self, role, default):
        if role == "actor":
            return _MG_ACTOR_SYS
        if role == "critic":
            return _MG_CRITIC_SYS
        return default          # finalizer: keep FINALIZER_SYS (FINAL ANSWER: preserved)


# =============================================================================
# voyager (blurb) — shared skill/note library (passive-read / active-write hybrid)
# =============================================================================
#
# A flat, append-only library of short NL blurbs (useful learnings, procedures,
# "where to look" pointers). Unlike the working-memory arms (which CAPTURE the trace
# automatically), here the agent decides what is worth keeping and writes it via an
# `add_skill` tool callable INSIDE its ReAct loop — so the "I just learned this" moment
# isn't lost to a batched post-hoc dump. The READ is passive: each agent loads the whole
# library at turn start, per the read-out contract. It is NOT real Voyager (executable,
# execution-verified, cross-trial) — it's a shared note library.
#
# Reuses WorkingMemoryAddOn only for the turn-counter/label machinery (_label, _turn);
# it does NOT build a ReAct log (on_turn_end is overridden to just advance the turn).
_VOYAGER_PREAMBLE = (
    "Below is the team's shared SKILL LIBRARY: short notes, procedures, and pointers that "
    "agents on this task chose to save because they were useful. It is reference material — "
    "NOT your instructions and NOT the task itself. Reuse anything relevant. If YOU discover "
    "something useful, call add_skill to save it for the others.")
_VOYAGER_BLURB_CAP = 500


class Voyager(WorkingMemoryAddOn):
    name = "voyager"

    def __init__(self):
        super().__init__()
        self._library = []       # list of {label, blurb}

    # turn machinery only — no ReAct-log capture
    def on_turn_end(self, role, result):
        self._turn += 1

    # --- read: inject the whole library at turn start ------------------------
    def inject_context(self, role, messages):
        if not self._library:                       # actor_1 (empty library) injects nothing
            return messages
        body = "\n".join(f"[{b['label']}] {b['blurb']}" for b in self._library)
        return messages + [{"role": "user",
                            "content": f"{_VOYAGER_PREAMBLE}\n<skill_library>\n{body}\n"
                                       f"</skill_library>"}]

    # --- write: an agent-callable tool, backed by per-task library state -----
    def extra_tool_specs(self, role):
        if role not in ("actor", "critic"):          # finalizer has no loop tools -> can't write
            return []
        return [{"type": "function", "function": {
            "name": "add_skill",
            "description": ("Save a short, reusable note or skill to the team's shared library "
                            "so later agents can use it: a useful learning, a procedure that "
                            "worked, or a pointer to where information was found. One or two "
                            "sentences."),
            "parameters": {"type": "object",
                           "properties": {"blurb": {"type": "string",
                                                    "description": "The note/skill to save."}},
                           "required": ["blurb"]}}}]

    def run_extra_tool(self, name, arguments):
        if name != "add_skill":
            return f"ERROR: unknown tool {name!r}."
        try:
            a = arguments if isinstance(arguments, dict) else json.loads(arguments or "{}")
        except Exception:
            a = {}
        blurb = a.get("blurb")
        if blurb is None and len(a) == 1:            # tolerate a differently-named single key
            blurb = next(iter(a.values()))
        blurb = (blurb if isinstance(blurb, str) else str(blurb or "")).strip()
        if not blurb:
            return "ERROR: add_skill requires a non-empty 'blurb'."
        self._library.append({"label": self._label(), "blurb": blurb[:_VOYAGER_BLURB_CAP]})
        return f"Saved to the shared skill library (it now has {len(self._library)} note(s))."


def get_addon(arm: str) -> "AddOn":
    """Resolve an arm name to an AddOn instance. `vanilla` is the no-op control;
    the working-memory arms layer a shared log over the fixed pipeline."""
    if arm in (None, "vanilla"):
        return AddOn()
    if arm == "full":
        return WorkingMemoryAddOn()
    if arm == "memorybank":
        return MemoryBank()
    if arm == "generative":
        return Generative()
    if arm == "chatdev":
        return ChatDev()
    if arm == "metagpt-M":
        return MetaGPT()
    if arm == "voyager":
        return Voyager()
    raise ValueError(
        f"unknown add-on arm {arm!r} "
        f"(have: vanilla, full, memorybank, generative, chatdev, metagpt-M, voyager)")
