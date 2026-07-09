"""The arm seam: the 7 policies over (edge payload, shared store).

An arm is a policy with exactly two decisions (PLAN "The seam"): what crosses an
edge, and what is written to / rendered from the ONE shared store. Nothing else
varies — `vanilla` must be byte-identical to a harness with no arm at all (asserted
by the prompt-diff audit in tests/test_arms_offline.py).

| arm          | edge payload                                   | store                       |
|--------------|------------------------------------------------|-----------------------------|
| vanilla      | natural artifact                               | —                           |
| full         | natural artifact                               | producers' raw transcripts  |
| sop          | typed schema (FINDINGS/EVIDENCE/VERDICT/NEXT)  | —                           |
| down         | payload + consumer-raised 1 challenge (if any) | —                           |
| board        | natural artifact                               | belief ledger, agent-written|
| extract      | natural artifact                               | same ledger, observer-written|
| board_inert  | natural artifact                               | write-tools, never rendered |

Sanctioned injection points (hygiene rule 8 — everything an arm may touch):
  1. the shared-state block (layer 3), via inject_context
  2. the wrap-up request on an edge, via wrapup_prompt
  3. arm-owned tool schemas, via extra_tool_specs (rule 2)
  4. the payload that crosses an edge, via edge_payload
Arms never touch the system prompt or the task layer.

Internal LLM machinery (extract's observer, down's challenger) runs through
run_agent/continue_agent with a NO-OP addon, so "run_agent is the only LLM caller"
holds and the machinery itself is never re-entered by the arm's own hooks. Those
calls share the run's usd_budget — the observer/challenge cost is on-meter (PLAN
"Known risks": no free lunch for our own arm).
"""
import json
import os
import re

import prompts
from store import BeliefLedger, TranscriptStore, parse_belief_lines, render_transcript


class AddOn:
    """No-op seam == the `vanilla` arm. Every hook is inert: no store, the natural
    artifact crosses each edge unchanged, no extra tools, nothing rendered."""

    name = "vanilla"

    def __init__(self):
        self.stats = {}                      # arm-adoption counters, persisted by run_task
        self._task = None
        self._role = None

    def bind(self, client, model, usd_budget):
        self.client, self.model, self.usd_budget = client, model, usd_budget

    def begin_task(self, task_prompt):
        """Called once per run before the topology starts; arms that need the task
        text for internal machinery (down's challenger) keep it here."""
        self._task = task_prompt

    def inject_context(self, role, messages):
        self._role = role                    # attribution for arm-owned tool writes
        return messages

    def on_turn_end(self, role, result):
        return None

    def extra_tool_specs(self, role):
        return []

    def run_extra_tool(self, name, arguments):
        return f"ERROR: no such tool {name!r}"

    def wrapup_prompt(self, kind, default):
        """The wrap-up ask on an edge ('handoff' | 'report'). vanilla: untouched."""
        return default

    def edge_payload(self, kind, producer_result, default):
        """`default` is the natural artifact the topology already computed (the
        hand-off note / report, truncation-guarded). vanilla passes it through."""
        return default

    def render(self):
        return ""

    def store_json(self):
        """The store's persistable contents (for traces); None when there is none."""
        return None


# One shared no-op instance for arm-internal machinery calls (observer/challenger):
# they must not re-enter the arm's own hooks (no store render inside the observer,
# no recursive on_turn_end), and vanilla's hooks are exactly that no-op.
_NOOP = AddOn()


def _args_dict(arguments):
    if isinstance(arguments, dict):
        return arguments
    try:
        return json.loads(arguments or "{}")
    except Exception:
        return {}


class _StoreArm(AddOn):
    """Shared plumbing for arms that render a store as layer 3. The block is injected
    as its own user message AFTER the task layers (rule 1: layer 3), wrapped in the
    rendering-contract preamble (rule 4). For persistent agents (dialogue) a re-render
    REPLACES the previous block rather than accumulating (the camel no-accumulation
    lesson): old blocks are recognized by the preamble's fixed prefix."""

    _BLOCK_PREFIX = prompts.STORE_PREAMBLE.split("{body}")[0].split("\n")[0]

    def inject_context(self, role, messages):
        self._role = role
        body = self.render()
        if not body:
            return messages
        messages = [m for m in messages
                    if not (m.get("role") == "user"
                            and (m.get("content") or "").startswith(self._BLOCK_PREFIX))]
        block = {"role": "user", "content": prompts.STORE_PREAMBLE.format(body=body)}
        return messages + [block]


# ------------------------------------------------------------------------------
# full — context family: is curation just cheap access to more info?
# ------------------------------------------------------------------------------
class FullAddOn(_StoreArm):
    """The producer's raw transcript is appended to the store at every handoff/report
    edge and rendered to every subsequent agent. The payload itself stays the natural
    artifact — `full` manipulates ACCESS, not the edge."""

    name = "full"

    def __init__(self):
        super().__init__()
        self.store = TranscriptStore()

    def edge_payload(self, kind, producer_result, default):
        # handoff/report/message = the work-product edges (assignment is a plan, not work)
        if kind in ("handoff", "report", "message") and producer_result is not None:
            self.store.add(producer_result)
            self.stats["transcripts_stored"] = len(self.store.blocks)
        return default

    def render(self):
        return self.store.render()

    def store_json(self):
        return [dict(agent=a, chars=len(b)) for a, b in self.store.blocks]


# ------------------------------------------------------------------------------
# sop — protocol family: format-on-the-edge (typed, publish-once, no persistence)
# ------------------------------------------------------------------------------
_SOP_FIELDS = ("FINDINGS", "EVIDENCE", "VERDICT", "NEXT_STEPS")
_SOP_HEADER = re.compile(r"^\s*(FINDINGS|EVIDENCE|VERDICT|NEXT_?STEPS|CONFIDENCE)\s*:\s*",
                         re.I | re.M)


def _sop_sections(text):
    """Split a wrap-up reply into its typed sections. Free text before the first
    header lands in FINDINGS (workers often preface the fields with a sentence)."""
    got = {}
    matches = list(_SOP_HEADER.finditer(text or ""))
    if matches and matches[0].start() > 0:
        got["FINDINGS"] = (text[:matches[0].start()]).strip()
    for m, nxt in zip(matches, matches[1:] + [None]):
        key = m.group(1).upper().replace("NEXTSTEPS", "NEXT_STEPS")
        if key == "NEXT_STEPS" or key in _SOP_FIELDS:
            body = text[m.end(): nxt.start() if nxt else len(text)].strip()
            got[key] = (got.get(key, "") + "\n" + body).strip() if key in got else body
    return got


def normalize_sop(text):
    """Force the payload into the typed schema: all four fields, canonical order,
    missing fields explicit. Returns (normalized_text, conformant_bool). Never
    silently drops content — unheadered text is kept as FINDINGS."""
    got = _sop_sections(text)
    if not got:
        got = {"FINDINGS": (text or "").strip()}
    conformant = all(f in got and got[f] for f in _SOP_FIELDS)
    lines = [f"{f}: {got.get(f) or '(not stated)'}" for f in _SOP_FIELDS]
    return "\n".join(lines), conformant


class SopAddOn(AddOn):
    """Typed edge payload. The wrap-up ask is retyped (SOP_HANDOFF_REQUEST) and the
    reply is normalized to the schema on crossing. Publish-once: no store, no
    revision, nothing persists past the edge."""

    name = "sop"

    def wrapup_prompt(self, kind, default):
        # retype BOTH edge asks — the relay hand-off and the (now free-text) hub report —
        # into the typed schema; that retyping is exactly what `sop` manipulates.
        if kind == "handoff":
            return prompts.SOP_HANDOFF_REQUEST
        if kind == "report":
            return prompts.SOP_REPORT_REQUEST
        return default

    def edge_payload(self, kind, producer_result, default):
        if kind not in ("handoff", "report") or default in (
                prompts.TRUNCATED_MARKER, prompts.REPORT_MARKER):
            return default
        normalized, ok = normalize_sop(default)
        self.stats["sop_payloads"] = self.stats.get("sop_payloads", 0) + 1
        self.stats["sop_conformant"] = self.stats.get("sop_conformant", 0) + int(ok)
        return normalized


# ------------------------------------------------------------------------------
# down — protocol family: a bounded challenge the CONSUMER decides to raise
# ------------------------------------------------------------------------------
_QUESTION_LINE = re.compile(r"^\s*QUESTION\s*:\s*(.+?)\s*$", re.M)
_DECLINE = {"none", "no question", "no", "n/a", "nothing", ""}


class DownAddOn(AddOn):
    """At every work-product edge the incoming consumer (a fresh agent holding the task +
    the payload) is asked whether it wants to raise ONE question — it decides freely, on
    judgment, with NO confidence threshold (the old θ-gate never fired: the model always
    self-reported high confidence). If it raises one, the producer answers ONCE (its
    working memory intact), and the Q/A is appended to the payload before it crosses.
    Both calls are tool-less and on-meter. No store, no persistence."""

    name = "down"

    def edge_payload(self, kind, producer_result, default):
        if kind not in ("handoff", "report") or default in (
                prompts.TRUNCATED_MARKER, prompts.REPORT_MARKER):
            return default
        self.stats["down_edges"] = self.stats.get("down_edges", 0) + 1
        if producer_result is None:
            return default
        question = self._ask_question(default)
        if not question:
            return default
        answer = self._answer(producer_result, question)
        if not answer:
            return default
        self.stats["down_challenges"] = self.stats.get("down_challenges", 0) + 1
        return prompts.DOWN_EXCHANGE_TEMPLATE.format(note=default, question=question,
                                                     answer=answer)

    def _ask_question(self, payload):
        from agent import run_agent
        ctx = [{"role": "user", "content": prompts.TASK_TEMPLATE.format(task=self._task or "")},
               {"role": "user", "content": prompts.CHALLENGE_NOTE_PREAMBLE.format(note=payload)}]
        res = run_agent("challenger", prompts.CHALLENGE_ASK_SYS, ctx, [], self.client,
                        self.model, _NOOP, usd_budget=self.usd_budget)
        m = _QUESTION_LINE.search(res.final or "")
        if not m or res.truncated:
            return None
        q = m.group(1).strip()
        return None if q.lower() in _DECLINE else q

    def _answer(self, producer_result, question):
        from agent import continue_agent
        res = continue_agent(producer_result,
                             prompts.CHALLENGE_ANSWER_REQUEST.format(question=question),
                             self.client, self.model, _NOOP, usd_budget=self.usd_budget)
        return res.final if res.final and not res.truncated else None


# ------------------------------------------------------------------------------
# board — state family: agent-written revisable belief ledger
# ------------------------------------------------------------------------------
_ADD_BELIEF_SPEC = dict(type="function", function=dict(
    name="add_belief", description=prompts.ADD_BELIEF_DESC,
    parameters=dict(type="object", properties=dict(
        object=dict(type="string", description="the thing the belief is about"),
        belief=dict(type="string", description="one concrete claim about it"),
        confidence=dict(type="number", description="how confident you are, 0 to 1"),
    ), required=["object", "belief", "confidence"])))

_REVISE_BELIEF_SPEC = dict(type="function", function=dict(
    name="revise_belief", description=prompts.REVISE_BELIEF_DESC,
    parameters=dict(type="object", properties=dict(
        belief_id=dict(type="string", description="the id of the belief to revise, e.g. 'b3'"),
        belief=dict(type="string", description="the corrected claim (omit if retracting)"),
        confidence=dict(type="number", description="your confidence in the correction, 0 to 1"),
        status=dict(type="string", description="'retracted' to retract instead of revise"),
    ), required=["belief_id"])))


class BoardAddOn(_StoreArm):
    """The belief ledger, written by the agents themselves via in-loop tools (rule 2:
    the capability is advertised in the tool schema, not the system prompt) and
    rendered to every agent at start. The natural artifact still crosses each edge —
    the ledger is a LATERAL channel, not a replacement payload."""

    name = "board"

    def __init__(self):
        super().__init__()
        self.ledger = BeliefLedger()

    def inject_context(self, role, messages):
        # layer-3 render block (board renders; board_inert overrides render() to "")
        messages = super().inject_context(role, messages)
        # the write incentive rides in the SOLVER system prompt (sanctioned rule-2 bend,
        # board arms only). The tool-less orchestrator reads the board but never writes,
        # so it is skipped. Idempotent: persistent (dialogue) agents re-enter each turn.
        if role != "orchestrator" and messages and messages[0].get("role") == "system":
            sysm = messages[0]
            if prompts.BOARD_WRITE_INCENTIVE not in (sysm.get("content") or ""):
                sysm["content"] = (sysm.get("content") or "") + prompts.BOARD_WRITE_INCENTIVE
        return messages

    def extra_tool_specs(self, role):
        # the orchestrator plans/merges only — no write-tools (PLAN: it has NO tools)
        if role == "orchestrator":
            return []
        return [_ADD_BELIEF_SPEC, _REVISE_BELIEF_SPEC]

    def run_extra_tool(self, name, arguments):
        a = _args_dict(arguments)
        author = self._role or "agent"
        if name == "add_belief":
            e = self.ledger.add(author, a.get("object"), a.get("belief"), a.get("confidence"))
            if not e["belief"]:
                return "ERROR: add_belief needs a non-empty 'belief'."
            self.stats["beliefs_added"] = self.stats.get("beliefs_added", 0) + 1
            return f"Recorded {e['id']}: {e['object']}: {e['belief']} (confidence {e['confidence']:.2f})"
        if name == "revise_belief":
            e = self.ledger.revise(author, a.get("belief_id"), belief=a.get("belief"),
                                   confidence=a.get("confidence"), status=a.get("status"))
            if e is None:
                have = ", ".join(x["id"] for x in self.ledger.active()) or "(board empty)"
                return f"ERROR: no belief with id {a.get('belief_id')!r}. Active ids: {have}"
            self.stats["beliefs_revised"] = self.stats.get("beliefs_revised", 0) + 1
            verb = "Retracted" if e["status"] == "retracted" else "Revised into"
            return f"{verb} {e['id']}: {e['object']}: {e['belief']}"
        return f"ERROR: no such tool {name!r}"

    def render(self):
        return self.ledger.render()

    def store_json(self):
        return self.ledger.to_json()


class BoardInertAddOn(BoardAddOn):
    """Tool-use confound control: the write-tools exist and work, but the store is
    NEVER rendered to anyone — any board-vs-vanilla gap that survives here is the
    tools' side effect on the writer, not shared state (headline cells only)."""

    name = "board_inert"

    def render(self):
        return ""


# ------------------------------------------------------------------------------
# extract — state family: the same ledger, reconstructed by an observer
# ------------------------------------------------------------------------------
OBSERVER_MAX_BELIEFS = int(os.environ.get("DUET_OBSERVER_MAX_BELIEFS", "8"))


class ExtractAddOn(_StoreArm):
    """Acquisition-mode ablation of `board`: the same ledger over the same rendering,
    but populated by an observer call at each edge event reading the producer's full
    trace (including its recovered <think>) — no agent cooperation needed. One extra
    model call per edge, charged to the run's usd_budget."""

    name = "extract"

    def __init__(self):
        super().__init__()
        self.ledger = BeliefLedger()

    def edge_payload(self, kind, producer_result, default):
        if kind in ("handoff", "report", "message") and producer_result is not None:
            self._observe(producer_result)
        return default

    def _observe(self, producer_result):
        from agent import run_agent
        log = render_transcript(producer_result, include_reasoning=True)
        if not log.strip():
            return
        sys_p = prompts.OBSERVER_SYS.format(max_beliefs=OBSERVER_MAX_BELIEFS)
        ctx = [{"role": "user", "content": prompts.OBSERVER_REQUEST.format(log=log)}]
        res = run_agent("observer", sys_p, ctx, [], self.client, self.model, _NOOP,
                        usd_budget=self.usd_budget)
        beliefs = parse_belief_lines(res.final)[:OBSERVER_MAX_BELIEFS]
        for kind, obj, belief, conf in beliefs:
            self.ledger.add(producer_result.role, obj, belief, conf, kind=kind)
        self.stats["observer_calls"] = self.stats.get("observer_calls", 0) + 1
        self.stats["beliefs_extracted"] = self.stats.get("beliefs_extracted", 0) + len(beliefs)

    def render(self):
        return self.ledger.render()

    def store_json(self):
        return self.ledger.to_json()


_ARMS = {"vanilla": AddOn, "full": FullAddOn, "sop": SopAddOn, "down": DownAddOn,
         "board": BoardAddOn, "board_inert": BoardInertAddOn, "extract": ExtractAddOn}


def get_addon(arm):
    """Instantiate an arm by name (a FRESH store per run)."""
    if arm not in _ARMS:
        raise KeyError(f"unknown arm {arm!r}; have {sorted(_ARMS)}")
    return _ARMS[arm]()
