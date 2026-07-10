"""Topology 2 — HUB (spatial asymmetry).

An orchestrator decomposes the task into 2–4 sub-questions; workers investigate them
BLIND to each other (fresh contexts, sequentially interleaved — informationally
identical to parallel); the orchestrator merges the reports and must finalize.
The asymmetry is the workers' hidden work
products: evidence found, entity disambiguations, dead ends. The IRL analogue is an
editor assigning fact-checks to reporters (PLAN, Topology 2).

Mechanics (PLAN):
  1. The orchestrator has NO tools — it plans and merges only (giving it tools lets it
     bypass the workers and the topology collapses).
  2. Round 1 — decompose: SUBQ: sentinel lines, 2–4 kept. A degenerate (<2) plan still
     runs — logged (`degenerate_plan`), reported, never silently patched.
  3. Round 2 — blind workers: each worker = fresh context [system, FULL original task,
     its assignment (+ arm store render)], full tool profile, budget B tool calls. Its
     terminal artifact is a structured report (FINDINGS/VERDICT/CONFIDENCE/EVIDENCE
     sentinel lines) produced by a single wrap-up continuation — same seam as the
     relay's hand-off note.
  4. Round 3 — merge: the orchestrator gets task + all attributed reports (+ store
     render) and must finalize with FINAL ANSWER: <answer|UNKNOWN>. There is NO
     follow-up channel in the base topology: backward/clarifying queries are an ARM
     mechanism (down), so the challenge family never leaks into vanilla.
  5. Sequential-blind execution lets each arm define exactly what leaks laterally:
     vanilla = nothing, `full` = prior workers' transcripts, board arms = the ledger.

Arm seam touchpoints (identical shape to relay.py): `addon.inject_context` renders the
store inside run_agent; `addon.edge_payload` may reshape what crosses the assignment
and report edges; `addon.wrapup_prompt` may retype the report ask. Vanilla: all no-ops.
"""
import re
from dataclasses import dataclass, field

from agent import run_agent, continue_agent
import prompts

DEFAULT_WORKER_BUDGET = 8
MAX_SUBQS = 4

_SUBQ_RE = re.compile(r"^\s*(?:[-*\d.)\s]*)SUBQ\s*:\s*(.+?)\s*$", re.M)
_CONF_RE = re.compile(r"^\s*CONFIDENCE\s*:\s*([0-9.]+)", re.M)


def parse_subqs(text, cap=MAX_SUBQS):
    """SUBQ: lines from a decompose reply, deduped in order, at most `cap` kept."""
    seen, out = set(), []
    for q in _SUBQ_RE.findall(text or ""):
        k = q.lower()
        if k not in seen:
            seen.add(k)
            out.append(q)
    return out[:cap]


def report_confidence(text):
    """The report's verbalized CONFIDENCE value, clamped to [0,1]; None if absent."""
    m = _CONF_RE.search(text or "")
    if not m:
        return None
    try:
        return max(0.0, min(1.0, float(m.group(1))))
    except ValueError:
        return None


def report_conformant(text):
    """Did the worker's report carry the asked-for sentinel fields? Logged per report
    (plan-quality style: reported, never silently patched)."""
    t = text or ""
    return all(f"{f}:" in t for f in ("FINDINGS", "VERDICT", "CONFIDENCE", "EVIDENCE"))


@dataclass
class HubResult:
    final: str                                    # merge's terminal text
    plan: list = field(default_factory=list)      # the assignment payloads that crossed
    reports: list = field(default_factory=list)   # the report payloads that crossed
    workers: list = field(default_factory=list)   # AgentResult per worker (report call)
    orch: list = field(default_factory=list)      # decompose, merge
    committed: bool = True
    budget_exceeded: bool = False
    degenerate_plan: bool = False                 # <2 sub-questions survived parsing

    @property
    def agents(self):
        return self.orch + self.workers

    @property
    def n_calls(self):
        return sum(a.n_steps for a in self.agents)

    @property
    def n_tool_calls(self):
        return sum(a.n_tool_calls for a in self.agents)

    @property
    def finish(self):
        return self.orch[-1].finish if self.orch else "stop"

    @property
    def report_markers(self):
        return sum(1 for r in self.reports if r == prompts.REPORT_MARKER)


def _task_layer(task_prompt):
    return {"role": "user", "content": prompts.TASK_TEMPLATE.format(task=task_prompt)}


def _assignment_layer(subq):
    return {"role": "user", "content": prompts.ASSIGNMENT_PREAMBLE.format(subq=subq)}


def _reports_layer(plan, reports):
    body = "\n\n".join(
        f"[worker_{i} · assigned: {subq}]\n{rep}"
        for i, (subq, rep) in enumerate(zip(plan, reports), 1))
    return {"role": "user", "content": prompts.REPORTS_PREAMBLE.format(reports=body)}


def _committed(final, finish):
    return "FINAL ANSWER:" in (final or "") or finish == "stop"


def _unknown(res, *, shape=None, **kw):
    r = shape or HubResult(final="FINAL ANSWER: UNKNOWN")
    r.final = "FINAL ANSWER: UNKNOWN"
    r.committed = True
    r.budget_exceeded = True
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def _run_worker(role, task_prompt, assignment, tool_names, client, model, addon,
                worker_budget, budget_tool_names, usd_budget, env):
    """One blind worker: investigate the assignment, then the report wrap-up. Returns
    (report AgentResult, the payload that crosses the report edge)."""
    ctx = [_task_layer(task_prompt), _assignment_layer(assignment)]
    res = run_agent(role, prompts.SOLVER_SYS, ctx, tool_names, client, model, addon,
                    tool_budget=worker_budget, budget_tool_names=budget_tool_names,
                    usd_budget=usd_budget, env=env)
    if usd_budget is not None and usd_budget.exceeded:
        return res, prompts.REPORT_MARKER
    rep = continue_agent(res, addon.wrapup_prompt("report", prompts.REPORT_REQUEST),
                         client, model, addon, usd_budget=usd_budget)
    usable = rep.final and not rep.truncated
    default = rep.final if usable else prompts.REPORT_MARKER
    return rep, addon.edge_payload("report", rep, default)


def run_hub(task_prompt, tool_names, client, model, addon, *,
            worker_budget=DEFAULT_WORKER_BUDGET, max_subqs=MAX_SUBQS,
            budget_tool_names=None, usd_budget=None, env=None) -> HubResult:
    out = HubResult(final="")

    # --- Round 1: decompose (tool-less orchestrator) ---------------------------
    dec = run_agent("orchestrator", prompts.ORCH_DECOMPOSE_SYS, [_task_layer(task_prompt)],
                    [], client, model, addon, usd_budget=usd_budget)
    out.orch.append(dec)
    if usd_budget is not None and usd_budget.exceeded:
        return _unknown(dec, shape=out)
    subqs = parse_subqs(dec.final, cap=max_subqs)
    if not subqs and not dec.truncated:            # format slip -> one constrained retry
        dec = continue_agent(dec, prompts.DECOMPOSE_RETRY, client, model, addon,
                             usd_budget=usd_budget)
        out.orch[-1] = dec
        subqs = parse_subqs(dec.final, cap=max_subqs)
    if not subqs:                                  # still nothing: degenerate 1-task plan
        subqs = [task_prompt]
    out.degenerate_plan = len(subqs) < 2

    # --- Round 2: blind workers (sequentially interleaved) ---------------------
    for i, subq in enumerate(subqs, 1):
        assignment = addon.edge_payload("assignment", dec, subq)
        out.plan.append(assignment)
        if usd_budget is not None and usd_budget.exceeded:
            out.reports.append(prompts.REPORT_MARKER)
            continue                               # keep plan/report lists aligned
        rep, payload = _run_worker(f"worker_{i}", task_prompt, assignment, tool_names,
                                   client, model, addon, worker_budget,
                                   budget_tool_names, usd_budget, env)
        out.workers.append(rep)
        out.reports.append(payload)
    if usd_budget is not None and usd_budget.exceeded:
        return _unknown(None, shape=out)

    # --- Round 3: merge (must finalize; no follow-up channel) -------------------
    mctx = [_task_layer(task_prompt), _reports_layer(out.plan, out.reports)]
    mer = run_agent("orchestrator", prompts.ORCH_MERGE_SYS, mctx, [], client, model,
                    addon, usd_budget=usd_budget)
    out.orch.append(mer)
    if usd_budget is not None and usd_budget.exceeded:
        return _unknown(None, shape=out)

    # Format slip OR a think-rabbit-hole (finish=='length' stores only the tiny
    # placeholder, so the retry context is clean) -> ONE constrained retry. Skipping
    # the retry on truncation lost 2/14 hub smokes to no_answer; only ctx_overflow
    # is unretryable (the context itself is full).
    if not mer.has_final_answer and mer.finish != "ctx_overflow":
        mer = continue_agent(mer, prompts.NO_FINAL_RETRY, client, model, addon,
                             usd_budget=usd_budget)
        out.orch[-1] = mer

    out.final = mer.final
    out.committed = _committed(mer.final, mer.finish)
    out.budget_exceeded = bool(usd_budget and usd_budget.exceeded)
    return out
