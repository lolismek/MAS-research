"""Topology 1 — RELAY (temporal asymmetry).

K identical shifts work the same task in sequence. Each shift is a fresh `run_agent`
context with a fixed tool-call budget B; at budget exhaustion it is asked (with its
working memory intact) for a free-text hand-off note, and the next shift starts from
[task, that note] — NEVER the predecessor's transcript. That destroyed-context edge is
the temporal asymmetry: shift k+1 inherits a conclusion without the evidence and
uncertainty behind it. The IRL analogue is a shift change / an agent hitting its context
window and handing to a fresh instance (PLAN, Topology 1).

Mechanics (PLAN):
  1. K=3 shifts; budget B tool calls per shift; FORCED hand-off at B (so "when to hand
     off" is never a confound). Early finish allowed: any shift may emit FINAL ANSWER and
     end the relay — skipped shifts show up on the efficiency axis, they are not prevented.
  2. The hand-off note is the natural artifact (the vanilla payload), produced by a single
     continuation call with HANDOFF_REQUEST.
  3. Shift k+1 context = [task, note (framed as a colleague's), + arm store-render]. Never
     the transcript.
  4. Shift K must terminate with FINAL ANSWER: <answer|UNKNOWN>.
  5. PDDL: the env persists across shifts (the world is the world); the note carries
     beliefs about world state. Budget bills only 'pddl_step' env steps.

The arm seam is untouched here except at two points: `addon.inject_context` (P2 renders
the store as layer 3 inside run_agent) and `addon.edge_payload` (P2 may reshape/replace
what crosses the edge). For vanilla both are no-ops, so this file IS the seamless relay.
"""
from dataclasses import dataclass, field

from agent import run_agent, continue_agent, AgentResult
import prompts

DEFAULT_K = 3
DEFAULT_BUDGET = 8          # tool calls (GAIA) / env steps (PDDL) per shift


@dataclass
class RelayResult:
    final: str                              # terminal shift's text (parse FINAL ANSWER from it)
    shifts: list = field(default_factory=list)   # one AgentResult per shift (latest, full transcript)
    notes: list = field(default_factory=list)    # what crossed each edge (len == shifts_used - 1)
    committed: bool = True
    budget_exceeded: bool = False

    # camel-PipelineResult-compatible surface, so run_task treats topologies uniformly.
    @property
    def agents(self):
        return self.shifts

    @property
    def shifts_used(self):
        return len(self.shifts)

    @property
    def n_calls(self):
        return sum(a.n_steps for a in self.shifts)

    @property
    def n_tool_calls(self):
        return sum(a.n_tool_calls for a in self.shifts)

    @property
    def finish(self):
        return self.shifts[-1].finish if self.shifts else "stop"


def _task_layer(task_prompt):
    """Layer 2: the benchmark question verbatim, delimited (hygiene rule 1)."""
    return {"role": "user", "content": prompts.TASK_TEMPLATE.format(task=task_prompt)}


def _note_layer(note):
    """The predecessor's hand-off note, framed as reference material (rules 3 & 4)."""
    return {"role": "user", "content": prompts.SUCCESSOR_PREAMBLE.format(note=note)}


def _committed(final, finish):
    """Did the terminal shift actually publish an answer? True if a FINAL ANSWER line is
    present, or it stopped cleanly (a clean short reply still asserted something). A
    truncated finalizer (length/step_cap/ctx_overflow) that left no line = no_answer."""
    return "FINAL ANSWER:" in (final or "") or finish == "stop"


def run_relay(task_prompt, tool_names, client, model, addon, *, k=DEFAULT_K,
              tool_budget=DEFAULT_BUDGET, budget_tool_names=None, usd_budget=None,
              env=None, initial_note=None) -> RelayResult:
    """`initial_note`: a pre-authored hand-off note injected before shift 1 — the
    temporal challenge-probe mechanism (PLAN "Challenge suite"): shift 1 then plays
    the successor inheriting OUR note (containing one plausible-but-wrong belief),
    and the probe asks whether the arm lets it detect/reject the planted belief."""
    shifts, notes = [], []
    prev_note = initial_note
    for i in range(k):
        is_last = i == k - 1
        role = f"shift_{i + 1}"
        ctx = [_task_layer(task_prompt)]
        if prev_note is not None:
            ctx.append(_note_layer(prev_note))

        res = run_agent(role, prompts.SOLVER_SYS, ctx, tool_names, client, model, addon,
                        tool_budget=tool_budget, budget_tool_names=budget_tool_names,
                        usd_budget=usd_budget, env=env)
        if usd_budget is not None and usd_budget.exceeded:
            shifts.append(res)
            return RelayResult(final="FINAL ANSWER: UNKNOWN", shifts=shifts, notes=notes,
                               committed=True, budget_exceeded=True)

        # Early finish: any shift that already committed ends the relay (mechanic 1).
        if res.has_final_answer:
            shifts.append(res)
            return RelayResult(final=res.final, shifts=shifts, notes=notes,
                               committed=_committed(res.final, res.finish))

        if is_last:
            # Shift K spent its budget without committing — force a commit (mechanic 4).
            fin = continue_agent(res, prompts.FINAL_COMMIT_REQUEST, client, model, addon,
                                 usd_budget=usd_budget)
            if not fin.has_final_answer and not fin.truncated and not (
                    usd_budget is not None and usd_budget.exceeded):
                fin = continue_agent(fin, prompts.NO_FINAL_RETRY, client, model, addon,
                                     usd_budget=usd_budget)
            shifts.append(fin)
            return RelayResult(final=fin.final, shifts=shifts, notes=notes,
                               committed=_committed(fin.final, fin.finish),
                               budget_exceeded=bool(usd_budget and usd_budget.exceeded))

        # Non-terminal shift: request the hand-off note, then decide what crosses the
        # edge. The wrap-up ask itself is an arm decision (sop retypes it, down appends
        # a confidence ask) — vanilla passes HANDOFF_REQUEST through untouched.
        note_res = continue_agent(res, addon.wrapup_prompt("handoff", prompts.HANDOFF_REQUEST),
                                  client, model, addon, usd_budget=usd_budget)
        # A truncated OR empty note must not cross the edge (rule 6) — the marker does.
        usable = note_res.final and not note_res.truncated
        default_payload = note_res.final if usable else prompts.TRUNCATED_MARKER
        payload = addon.edge_payload("handoff", note_res, default_payload)
        shifts.append(note_res)        # note_res.transcript is the full shift incl. the note
        notes.append(payload)
        prev_note = payload
        if usd_budget is not None and usd_budget.exceeded:
            return RelayResult(final="FINAL ANSWER: UNKNOWN", shifts=shifts, notes=notes,
                               committed=True, budget_exceeded=True)

    # Unreachable (the is_last branch always returns), but keep the type total.
    last = shifts[-1]
    return RelayResult(final=last.final, shifts=shifts, notes=notes,
                       committed=_committed(last.final, last.finish))
