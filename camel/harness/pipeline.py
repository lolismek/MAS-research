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

ACTOR_SYS = (
    "You are a problem solver. Solve the task, using the available tools when they "
    "help. End your reply with a line:\nFINAL ANSWER: <your answer>")

CRITIC_SYS = (
    "You review another agent's proposed answer to a task. Verify it — use the "
    "available tools to recompute or re-check sources rather than trusting it. "
    "If it is correct, reply with exactly: Agree\n"
    "Otherwise give brief, concrete feedback (at most 3 sentences).")

FINALIZER_SYS = (
    "You produce the final answer to a task, given a proposed answer and a "
    "critique of it. If the critique is sound, fix the answer. If you cannot "
    "verify the answer is correct, give UNKNOWN. End with a line:\n"
    "FINAL ANSWER: <your answer>")


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

    # critic verifies actor_2
    cr_ctx = task + _user(f"Proposed answer:\n\n{actor_2.final}\n\nReview it.")
    critic = run_agent("critic", CRITIC_SYS, cr_ctx, tool_names, client, model, addon)

    # edge 2: finalizer sees actor_2's answer + the critique
    fin_ctx = task + _user(f"Proposed answer:\n\n{actor_2.final}\n\n"
                           f"Critique:\n\n{critic.final}\n\nGive the final answer.")
    finalizer = run_agent("finalizer", FINALIZER_SYS, fin_ctx, tool_names, client, model, addon)

    return PipelineResult(final=finalizer.final,
                          agents=[actor_1, actor_2, critic, finalizer])
