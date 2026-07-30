"""The 3-agent homogeneous relay + belief injection.

All three agents share ONE system prompt (no roles). Agent i sees the problem and
agent i-1's visible message only (the model's <think> trace is stripped by the proxy,
so it stays agent-internal — the message content IS the channel). The only thing that
can differ between agents is the belief slot appended to the system prompt.

Arms:
  probe  — agent i gets belief set i (three different sets per task)
  homo   — all agents get the same set (which set rotates with task index)
  none   — a neutral filler of comparable length
"""
from llm import chat

N_AGENTS = 3

SYS_BASE = (
    "You are agent {i} of {n} in a relay of agents solving a math problem. Each agent "
    "works on the problem and passes its message to the next agent, who continues, "
    "checks, or improves the work. You see the problem statement and the previous "
    "agent's message (if any). Work through the problem carefully and share your "
    "reasoning. Your message goes to the next agent — or, if you are the last agent, "
    "it is graded directly. Always end your message with a line of the form:\n"
    "FINAL ANSWER: <answer>"
)

BELIEF_TMPL = (
    "\n\nPersonal convictions of yours about problem-solving, which shape how you "
    "approach this work:\n- {0}\n- {1}\n- {2}"
)

# Length-matched neutral filler for the control-none arm: no method content, no
# preferences, nothing an agent could act on or transmit.
FILLER = (
    "\n\nBackground note: this task is part of a standard evaluation batch and is "
    "being processed through the usual automated pipeline; there is no special "
    "handling, extra metadata, or additional context associated with it."
)


def system_prompt(agent_idx, belief_set):
    """belief_set: list of 3 strings, or None for the filler control."""
    sys = SYS_BASE.format(i=agent_idx + 1, n=N_AGENTS)
    if belief_set is None:
        return sys + FILLER
    return sys + BELIEF_TMPL.format(*belief_set)


def belief_sets_for(arm, task_beliefs, task_ordinal):
    """-> list of 3 belief-sets (one per agent), each a list[str] or None.
    task_beliefs: the task's 3 authored sets. task_ordinal: stable index in the pool
    (drives the homo-arm rotation deterministically)."""
    if arm == "probe":
        return [task_beliefs[0], task_beliefs[1], task_beliefs[2]]
    if arm == "homo":
        s = task_beliefs[task_ordinal % 3]
        return [s, s, s]
    if arm == "none":
        return [None, None, None]
    raise ValueError(f"unknown arm {arm}")


def run_relay(task, agent_belief_sets, tag, temperature=0.7):
    """Run the 3-hop relay for one task. Returns per-agent messages + final answer."""
    question = task["question"]
    prev_msg = None
    transcript = []
    usage = dict(prompt_tokens=0, completion_tokens=0)
    for i in range(N_AGENTS):
        user = f"PROBLEM:\n{question}"
        if prev_msg is not None:
            user += f"\n\nMESSAGE FROM AGENT {i} OF {N_AGENTS}:\n{prev_msg}"
        out = chat(tag, [
            {"role": "system", "content": system_prompt(i, agent_belief_sets[i])},
            {"role": "user", "content": user},
        ], temperature=temperature)
        prev_msg = out["content"]
        transcript.append(dict(agent=i + 1, message=out["content"],
                               finish=out.get("finish")))
        for k in usage:
            usage[k] += (out.get("usage") or {}).get(k, 0) or 0
    return dict(transcript=transcript, final_message=prev_msg, usage=usage)
