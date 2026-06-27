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

    @property
    def n_calls(self):
        return sum(a.n_steps for a in self.agents)

    @property
    def n_tool_calls(self):
        return sum(a.n_tool_calls for a in self.agents)


def _user(text):
    return [{"role": "user", "content": text}]


def run_pipeline(task_prompt, tool_names, client, model, addon) -> PipelineResult:
    task = _user(task_prompt)

    actor_1 = run_agent("actor", ACTOR_SYS, task, tool_names, client, model, addon)

    # edge 1: actor_2 sees actor_1's answer
    a2_ctx = task + _user(f"Another solver proposed this answer:\n\n{actor_1.final}\n\n"
                          "Consider it, then give your own answer.")
    actor_2 = run_agent("actor", ACTOR_SYS, a2_ctx, tool_names, client, model, addon)

    # critic verifies actor_2 (keeps tools so it can actually check, not re-solve)
    cr_ctx = task + _user(f"Proposed answer to verify:\n\n{actor_2.final}")
    critic = run_agent("critic", CRITIC_SYS, cr_ctx, tool_names, client, model, addon)

    # edge 2: finalizer adjudicates BOTH candidates + the critique, with NO tools
    # (so it decides from evidence and can't re-solve). Seeing both actors lets it
    # abstain when they disagree and the critique didn't settle it.
    fin_ctx = task + _user(
        f"Candidate answer A (solver 1):\n\n{actor_1.final}\n\n"
        f"Candidate answer B (solver 2):\n\n{actor_2.final}\n\n"
        f"Verifier's critique of B:\n\n{critic.final}\n\nDecide the final answer.")
    finalizer = run_agent("finalizer", FINALIZER_SYS, fin_ctx, [], client, model, addon)

    return PipelineResult(final=finalizer.final,
                          agents=[actor_1, actor_2, critic, finalizer])
