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

# v2: budget-capped handoff relay. Each agent's output (thinking included) is capped
# below what a full solo solve needs, so work MUST be split across the channel. The
# prompt forces early externalization — a mid-think truncation yields an empty channel
# message (the proxy strips unterminated <think>), so agents are told to stop
# reasoning early and write partial progress down.
SYS_HANDOFF = (
    "You are agent {i} of {n} in a relay of agents solving a math problem together. "
    "Your output budget is strictly limited — you do NOT have room to solve the whole "
    "problem from scratch, and your reply is cut off if too long. Keep your private "
    "reasoning very brief; put your work in the visible message instead. Build on the "
    "previous agent's partial work (if any), advance the solution as far as your "
    "budget allows, then STOP and write a compact handoff note: established results, "
    "key intermediate values, and exactly what remains to be done. End your message "
    "with the line:\nHANDOFF: <one-line summary of state>\n"
    "Or, if the final answer is already established:\nFINAL ANSWER: <answer>"
)
SYS_HANDOFF_LAST = (
    "You are agent {i} of {n}, the LAST agent in a relay of agents solving a math "
    "problem together. The previous agents have made partial progress. Your output "
    "budget is strictly limited, so keep your private reasoning very brief. Use the "
    "previous agent's handoff to finish the problem. You MUST commit to an answer. "
    "End your message with the line:\nFINAL ANSWER: <answer>"
)

# v2f: FEVER two-way claim verification, same capped-handoff mechanics as v2.
SYS_FEVER = (
    "You are agent {i} of {n} in a relay of agents verifying a factual claim "
    "together. Your output budget is strictly limited, so keep your private "
    "reasoning very brief; put your work in the visible message instead. Build on "
    "the previous agent's notes (if any): recall relevant facts, weigh whether the "
    "claim holds, and write a compact note for the next agent — what you recalled, "
    "your current leaning, and what remains uncertain. End your message with the "
    "line:\nLEANING: <SUPPORTS or REFUTES, plus one clause of justification>"
)
SYS_FEVER_LAST = (
    "You are agent {i} of {n}, the LAST agent in a relay of agents verifying a "
    "factual claim together. Your output budget is strictly limited, so keep your "
    "private reasoning very brief. Weigh the previous agents' notes against your "
    "own knowledge and commit to a verdict. End your message with the line:\n"
    "FINAL ANSWER: <SUPPORTS or REFUTES>"
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


def system_prompt(agent_idx, belief_set, variant="v1"):
    """belief_set: list of 3 strings, or None for the filler control."""
    if variant == "v2f":
        base = SYS_FEVER_LAST if agent_idx == N_AGENTS - 1 else SYS_FEVER
    elif variant == "v2":
        base = SYS_HANDOFF_LAST if agent_idx == N_AGENTS - 1 else SYS_HANDOFF
    else:
        base = SYS_BASE
    sys = base.format(i=agent_idx + 1, n=N_AGENTS)
    if belief_set is None:
        return sys + FILLER
    return sys + BELIEF_TMPL.format(*belief_set)


def belief_sets_for(arm, task_beliefs, task_ordinal, rotate_probe=False):
    """-> list of 3 belief-sets (one per agent), each a list[str] or None.
    task_beliefs: the task's 3 authored sets. task_ordinal: stable index in the pool
    (drives the homo-arm rotation deterministically). rotate_probe: rotate set->agent
    assignment by ordinal (v2f directional sets: deconfounds flavor from position)."""
    if arm == "probe":
        if rotate_probe:
            r = task_ordinal % 3
            return [task_beliefs[(0 + r) % 3], task_beliefs[(1 + r) % 3],
                    task_beliefs[(2 + r) % 3]]
        return [task_beliefs[0], task_beliefs[1], task_beliefs[2]]
    if arm == "homo":
        s = task_beliefs[task_ordinal % 3]
        return [s, s, s]
    if arm == "none":
        return [None, None, None]
    raise ValueError(f"unknown arm {arm}")


def run_relay(task, agent_belief_sets, tag, temperature=0.7, variant="v1",
              max_tokens=16000):
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
            {"role": "system", "content": system_prompt(i, agent_belief_sets[i],
                                                        variant=variant)},
            {"role": "user", "content": user},
        ], temperature=temperature, max_tokens=max_tokens)
        prev_msg = out["content"]
        transcript.append(dict(agent=i + 1, message=out["content"],
                               finish=out.get("finish")))
        for k in usage:
            usage[k] += (out.get("usage") or {}).get(k, 0) or 0
    return dict(transcript=transcript, final_message=prev_msg, usage=usage)
