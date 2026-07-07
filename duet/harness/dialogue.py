"""Topology 3 — DIALOGUE (the mixture case; least asymmetry).

Two IDENTICAL persistent agents alternate turns on one task. Each turn is a full
run_agent inner loop with a bounded per-turn tool budget; the terminal artifact is a
message to the peer. The peer sees ONLY the message — the tool trail stays private —
but both agents keep their ENTIRE context for the whole task (nobody's context is
destroyed), so hidden information is only intra-turn work products. That anchors the
gradient prediction: the board's effect should be smallest here (PLAN, Topology 3).

Mechanics (PLAN):
  1. Turns alternate peer_A / peer_B; each turn = run_agent resumed on that agent's
     persistent transcript (fresh per-turn budget).
  2. Only the message crosses; a turn with no usable message crosses MESSAGE_MARKER
     (rule 6).
  3. Termination: a message containing FINAL ANSWER is a proposal; the peer is asked
     to ratify (DECISION: agree -> done, the proposer's answer stands) or contest
     (continue). ONE contest is allowed per run — after it is spent, the next proposal
     is accepted as-is. Hard cap T turns, then the agent whose turn it is must
     finalize or abstain (FINAL_COMMIT_REQUEST).
  4. Every message is an edge event: `addon.edge_payload("message", ...)`; the store
     render is refreshed at each turn start via inject_context (a re-render REPLACES
     the previous block — the no-accumulation contract).
"""
import re
from dataclasses import dataclass, field

from agent import run_agent, continue_agent
import prompts

DEFAULT_T = 8
DEFAULT_TURN_BUDGET = 4

_DECISION_RE = re.compile(r"^\s*DECISION\s*:\s*(agree|contest)", re.I | re.M)


@dataclass
class DialogueResult:
    final: str = ""
    turns: list = field(default_factory=list)      # AgentResult per turn, in order
    messages: list = field(default_factory=list)   # the payloads that crossed
    proposals: int = 0
    contests: int = 0
    ratified: bool = False                          # ended by peer agreement
    committed: bool = True
    budget_exceeded: bool = False
    states: dict = field(default_factory=dict)      # role -> final persistent transcript

    @property
    def agents(self):
        return self.turns

    @property
    def turns_used(self):
        return len(self.turns)

    @property
    def n_calls(self):
        return sum(a.n_steps for a in self.turns)

    @property
    def n_tool_calls(self):
        return sum(a.n_tool_calls for a in self.turns)

    @property
    def finish(self):
        return self.turns[-1].finish if self.turns else "stop"


def _task_layer(task_prompt):
    return {"role": "user", "content": prompts.TASK_TEMPLATE.format(task=task_prompt)}


def _committed(final, finish):
    return "FINAL ANSWER:" in (final or "") or finish == "stop"


def _decision(text):
    m = _DECISION_RE.search(text or "")
    return m.group(1).lower() if m else None


def run_dialogue(task_prompt, tool_names, client, model, addon, *, t_max=DEFAULT_T,
                 turn_budget=DEFAULT_TURN_BUDGET, budget_tool_names=None,
                 usd_budget=None, env=None) -> DialogueResult:
    out = DialogueResult()
    states = {"peer_A": None, "peer_B": None}       # persistent transcripts
    out.states = states                             # same dict object: mutated in place,
    pending = None                                  # so every return path sees the final
    pending_proposal = False                        # per-agent transcripts

    for t in range(1, t_max + 1):
        role = "peer_A" if t % 2 else "peer_B"
        is_last = t == t_max

        # -- incoming user messages for this turn (rule 3: only what the next action needs)
        incoming = []
        if states[role] is None:
            incoming.append(_task_layer(task_prompt))
        if pending is None:                          # first move of the whole dialogue
            incoming.append({"role": "user", "content": prompts.DIALOGUE_KICKOFF})
        else:
            incoming.append({"role": "user",
                             "content": prompts.PEER_PREAMBLE.format(message=pending)})
            if pending_proposal:
                incoming.append({"role": "user", "content": prompts.RATIFY_REQUEST})

        if states[role] is None:
            res = run_agent(role, prompts.SOLVER_SYS, incoming, tool_names, client, model,
                            addon, tool_budget=turn_budget,
                            budget_tool_names=budget_tool_names, usd_budget=usd_budget,
                            env=env)
        else:
            res = run_agent(role, prompts.SOLVER_SYS, [], tool_names, client, model,
                            addon, tool_budget=turn_budget,
                            budget_tool_names=budget_tool_names, usd_budget=usd_budget,
                            env=env, resume=states[role] + incoming)
        if usd_budget is not None and usd_budget.exceeded:
            out.turns.append(res)
            states[role] = res.transcript
            out.final, out.committed, out.budget_exceeded = "FINAL ANSWER: UNKNOWN", True, True
            break

        # -- a turn that spent its budget without a message is asked for one (the seam)
        if not res.final or res.truncated:
            res = continue_agent(res, addon.wrapup_prompt("message", prompts.TURN_MESSAGE_REQUEST),
                                 client, model, addon, usd_budget=usd_budget)
        out.turns.append(res)
        states[role] = res.transcript

        usable = res.final and not res.truncated
        default = res.final if usable else prompts.MESSAGE_MARKER
        payload = addon.edge_payload("message", res, default)
        out.messages.append(payload)

        # -- ratification of the peer's standing proposal
        if pending_proposal:
            d = _decision(payload)
            if d == "agree":
                out.ratified = True
                out.final = pending                  # the proposer's answer stands
                out.committed = True
                out.budget_exceeded = bool(usd_budget and usd_budget.exceeded)
                return out
            if d == "contest":
                out.contests += 1

        # -- does THIS message propose?
        proposes = "FINAL ANSWER:" in payload
        if proposes:
            out.proposals += 1
            if out.contests >= 1 or is_last:
                # the single contest is spent (or no turns remain): the proposal stands
                out.final = payload
                out.committed = _committed(res.final, res.finish)
                out.budget_exceeded = bool(usd_budget and usd_budget.exceeded)
                return out
            pending, pending_proposal = payload, True
            continue

        if is_last:
            # cap reached without a standing proposal: this agent must finalize or abstain
            fin = continue_agent(res, prompts.FINAL_COMMIT_REQUEST, client, model, addon,
                                 usd_budget=usd_budget)
            if not fin.has_final_answer and not fin.truncated and not (
                    usd_budget is not None and usd_budget.exceeded):
                fin = continue_agent(fin, prompts.NO_FINAL_RETRY, client, model, addon,
                                     usd_budget=usd_budget)
            out.turns[-1] = fin
            states[role] = fin.transcript
            out.final = fin.final
            out.committed = _committed(fin.final, fin.finish)
            out.budget_exceeded = bool(usd_budget and usd_budget.exceeded)
            break

        pending, pending_proposal = payload, False

    if not out.final:                                # defensive: loop exhausted uncommitted
        out.final = "FINAL ANSWER: UNKNOWN"
        out.committed = True
    return out
