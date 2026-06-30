"""The MAS: a 4-agent linear pipeline (LatentMem-flattened "CAMEL").

    actor_1 ──▶ actor_2 ──▶ critic ──▶ finalizer
             (edge 1)    (edge 2 carries actor_2's answer + the critique)

Two near-identical actors (actor_2 sees actor_1 → a revision pass), a critic that
VERIFIES (it gets tools, so it can recompute/recheck rather than rubber-stamp),
and a finalizer that merges answer+critique into the published answer (and may
abstain). Each agent runs its own internal loop (agent.py). The two edges are the
only inter-agent hand-offs — and the only places the AddOn (belief board, memory)
will later inject sincere state; for vanilla, just the polished `.final` crosses.

Prompts are deliberately tiny: Qwen3.6 reasons on its own (the proxy strips the
<think> trace), so we don't add CoT scaffolding.
"""
from dataclasses import dataclass

from agent import run_agent, AgentResult

# Each role has a DISTINCT objective (generate / verify / adjudicate), not the same
# "solve" job. Capability follows the objective: actors + critic get tools (the
# critic needs them to VERIFY), the finalizer gets none (so it can only decide, not
# re-solve). See README "Roles".
ACTOR_SYS = (
    "You are a problem solver. Solve the task, using the available tools when they "
    "help. End your reply with a line:\nFINAL ANSWER: <your answer>")

CRITIC_SYS = (
    "You VERIFY another agent's proposed answer. Do NOT solve the task from scratch "
    "or produce your own answer — your job is only to check theirs. Use the tools to "
    "verify the specific claims and steps IN the proposed answer: recompute its "
    "arithmetic, re-check its factual claims. If every claim checks out, reply with "
    "exactly: Agree\nOtherwise name the specific claim(s) that are wrong and the "
    "correct value, in at most 3 sentences.")

FINALIZER_SYS = (
    "You DECIDE the final answer from evidence you are given: candidate answers and a "
    "verifier's critique of them. Do NOT solve the task yourself and do NOT use tools "
    "— decide only from the evidence. If the critique confirms a candidate, output it. "
    "If the candidates disagree or the critique found an unresolved error and the "
    "evidence does not clearly settle the answer, output UNKNOWN. End with a line:\n"
    "FINAL ANSWER: <your answer, or UNKNOWN>")


@dataclass
class PipelineResult:
    final: str                 # finalizer's published text (parse FINAL ANSWER from this)
    agents: list               # [actor_1, actor_2, critic, finalizer] AgentResults
    budget_exceeded: bool = False   # task hit the per-task USD cap -> short-circuited to UNKNOWN

    @property
    def n_calls(self):
        return sum(a.n_steps for a in self.agents)

    @property
    def n_tool_calls(self):
        return sum(a.n_tool_calls for a in self.agents)

    @property
    def committed(self):
        """Did the pipeline actually publish an answer? Only False when the finalizer
        emitted NO 'FINAL ANSWER:' line AND was cut off (truncated/looped) — i.e. a real
        non-answer. A short reply that finished cleanly but slipped the format still
        *asserted* something, so it stays a (possibly wrong) committed answer, not
        no_answer — otherwise we'd hide genuine confident-wrong hallucinations."""
        return "FINAL ANSWER:" in (self.final or "") or self.finish == "stop"

    @property
    def finish(self):
        return self.agents[-1].finish if self.agents else "stop"


def _aborted(agents):
    """Per-task budget blown mid-pipeline: publish an honest UNKNOWN, keep partial trace."""
    return PipelineResult(final="FINAL ANSWER: UNKNOWN", agents=agents, budget_exceeded=True)


def _user(text):
    return [{"role": "user", "content": text}]


def _handoff(agent):
    """What crosses an inter-agent edge. An agent that was cut off mid-think (truncated)
    never reached a usable answer — its `.final` is raw, unterminated reasoning. Don't
    propagate that: it both balloons the downstream agent's context (the 28k leak that
    overflowed the next agent) AND isn't trustworthy (a cut-off derivation is how a
    confident-wrong answer slips through). Hand over a short marker instead, so a
    downstream agent treats it as 'no answer' rather than inheriting the garbage."""
    if agent.truncated:
        return "[the previous agent ran out of space before producing a usable answer]"
    return agent.final


def run_pipeline(task_prompt, tool_names, client, model, addon, budget=None, env=None) -> PipelineResult:
    task = _user(task_prompt)
    # The AddOn may swap a role's system prompt (metagpt-M); for every other arm
    # `system_prompt` returns the default unchanged.
    actor_sys = addon.system_prompt("actor", ACTOR_SYS)
    critic_sys = addon.system_prompt("critic", CRITIC_SYS)
    finalizer_sys = addon.system_prompt("finalizer", FINALIZER_SYS)

    actor_1 = run_agent("actor", actor_sys, task, tool_names, client, model, addon, budget=budget, env=env)
    if budget is not None and budget.exceeded:
        return _aborted([actor_1])

    # edge 1 (actor_1 -> actor_2): actor_2 sees actor_1's answer
    a2_ctx = task + _user(f"Another solver proposed this answer:\n\n{_handoff(actor_1)}\n\n"
                          "Consider it, then give your own answer.")
    actor_2 = run_agent("actor", actor_sys, a2_ctx, tool_names, client, model, addon, budget=budget, env=env)
    if budget is not None and budget.exceeded:
        return _aborted([actor_1, actor_2])

    # edge 2 (actor_2 -> critic): critic verifies actor_2 (keeps tools to check, not re-solve)
    cr_ctx = task + _user(f"Proposed answer to verify:\n\n{_handoff(actor_2)}")
    critic = run_agent("critic", critic_sys, cr_ctx, tool_names, client, model, addon, budget=budget, env=env)
    if budget is not None and budget.exceeded:
        return _aborted([actor_1, actor_2, critic])

    # edge 3 (critic -> finalizer) + skip-edges (actor_1, actor_2 -> finalizer):
    # finalizer adjudicates BOTH candidates + the critique, with NO tools (so it
    # decides from evidence and can't re-solve). Seeing both actors lets it abstain
    # when they disagree and the critique didn't settle it.
    fin_ctx = task + _user(
        f"Candidate answer A (solver 1):\n\n{_handoff(actor_1)}\n\n"
        f"Candidate answer B (solver 2):\n\n{_handoff(actor_2)}\n\n"
        f"Verifier's critique of B:\n\n{_handoff(critic)}\n\nDecide the final answer.")
    finalizer = run_agent("finalizer", finalizer_sys, fin_ctx, [], client, model, addon, budget=budget)

    # If the finalizer rambled past the token cap or slipped the format, it left no
    # 'FINAL ANSWER:' line — and a present-but-unparsed answer would be miscounted as a
    # confident miss. Give it ONE constrained retry that can ONLY emit the line.
    if "FINAL ANSWER:" not in (finalizer.final or "") and not (budget is not None and budget.exceeded):
        retry_ctx = fin_ctx + _user(
            "You did not output a 'FINAL ANSWER:' line. Decide now from the evidence "
            "above and output EXACTLY one line, nothing else:\nFINAL ANSWER: <answer, "
            "or UNKNOWN>")
        finalizer = run_agent("finalizer", finalizer_sys, retry_ctx, [], client, model,
                              addon, budget=budget)

    return PipelineResult(final=finalizer.final,
                          agents=[actor_1, actor_2, critic, finalizer])
