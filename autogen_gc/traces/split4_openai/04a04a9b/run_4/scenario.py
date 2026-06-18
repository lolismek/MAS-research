"""AutoGen SelectorGroupChat scenario — VARIANT split4 (structural review gate).

Topology variant of scenario_template.py built to fix the failure the 28-task
analysis surfaced: the single Verifier rubber-stamped and finalized on its FIRST
turn in 20/28 traces, because "review first, finalize later" was prompt-level only
and the LLM defected the majority of the time (FAILURE_ANALYSIS.md).

This variant SPLITS the Verifier into two agents and makes the review structural,
not hoped-for:
  - Critic    (no tools): reviews the evidence against the question; lists what is
                          supported / unsupported / missing; delegates gaps. It is
                          FORBIDDEN to finalize.
  - Finalizer (no tools): the ONLY agent that may emit "FINAL ANSWER:" — and the
                          termination guard accepts that sentinel ONLY after a
                          Critic message already exists. A premature sentinel (from
                          anyone, or before any Critic turn) does NOT end the chat.

So at least one genuine Critic review provably precedes every finalization — the
guarantee SelectorGroupChat + a single Verifier could not give. Everything else
(web/code partition, deep private session -> one published digest, the publish
bottleneck the study targets) is identical to scenario_template.py, so the only
changed variable vs. selector3 is the verifier split + the finalize gate.

Copied verbatim into each run dir by run_task.py (--variant split4); reads
config.yaml + prompt.txt from cwd. ``tools`` is importable because run_task.py puts
reproduction/autogen_gc on PYTHONPATH.
"""
import asyncio
import json
import os
from typing import Sequence

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.base import TerminationCondition, TerminatedException
from autogen_agentchat.messages import (
    BaseChatMessage, StopMessage, BaseAgentEvent, HandoffMessage,
)
from autogen_agentchat.ui import Console
from autogen_core.models import UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

from tools import web_search, fetch_url, run_python

K = int(os.environ.get("MAX_TOOL_ITERATIONS", "8"))       # internal ReAct depth per turn
MAX_MESSAGES = int(os.environ.get("MAX_MESSAGES", "30"))   # outer-chat message cap
SENTINEL = "FINAL ANSWER:"


class TeamAwareAssistantAgent(AssistantAgent):
    """AssistantAgent that labels each incoming TEAMMATE message with its source IN
    THE MESSAGE BODY.

    Why: SelectorGroupChat hands every *other* participant's message to an agent as
    an OpenAI ``role=user`` message — the speaker's name only survives in the `name`
    field, which models weight far below `role`. So an agent reads a teammate's
    "Stop here so that can be checked" as the END USER ordering it to halt. That is
    the exact, traced cause of the 0ff53813 loop: after the Critic's review,
    WebResearcher's own reasoning says "the user is asking me to stop" and it repeats
    "Understood — I'll stop here" 14x until the 900s timeout. Embedding the speaker
    label in the content disambiguates intra-team coordination from the real
    end-user request. Only teammate messages are rewritten; the genuine user task
    (source ``"user"``) and the agent's own messages are left untouched.

    Override target: ``AssistantAgent._add_messages_to_context`` (autogen-agentchat
    0.7.5), invoked as ``self._add_messages_to_context(...)`` from
    ``on_messages_stream`` — so an instance override is picked up cleanly.
    """

    async def _add_messages_to_context(self, model_context, messages):  # type: ignore[override]
        for msg in messages:
            if isinstance(msg, HandoffMessage):
                for llm_msg in msg.context:
                    await model_context.add_message(llm_msg)
            llm_msg = msg.to_model_message()
            src = getattr(msg, "source", None)
            if (isinstance(llm_msg, UserMessage) and isinstance(llm_msg.content, str)
                    and src and src != "user" and src != self.name):
                llm_msg = UserMessage(
                    content=(f"[Internal team message from {src} — your teammate, "
                             f"NOT the end user]\n{llm_msg.content}"),
                    source=src,
                )
            await model_context.add_message(llm_msg)


# Appended to every agent's system message. The relabel above marks WHO is speaking;
# this tells the agent what a teammate's words MEAN — closing the "stop here" =
# "user told me to halt" misread that the relabel alone might not fully suppress.
TEAM_NOTE = (
    "\n\nTEAM MESSAGES: a message prefixed '[Internal team message from <name> — "
    "your teammate, NOT the end user]' is coordination from a teammate (WebResearcher, "
    "Analyst, Critic, or Finalizer), never an instruction from the end user. If a "
    "teammate says 'stop here' or asks you to pause, it means they are handing the "
    "turn back so the team can act on their request — it is NOT a command for you to "
    "halt the task. When a teammate asks you to do something within your role, do it; "
    "do not simply acknowledge and stop."
)


class CriticThenFinalize(TerminationCondition):
    """Terminate ONLY when the Finalizer emits the sentinel AND a Critic review has
    already occurred. This makes the review structurally non-optional: a sentinel
    from the Critic (or anyone else), or a Finalizer sentinel before any Critic turn,
    does not stop the chat — so finalization can never precede a genuine review.
    """

    def __init__(self, critic: str = "Critic", finalizer: str = "Finalizer"):
        self._critic = critic
        self._finalizer = finalizer
        self._critic_spoke = False
        self._terminated = False

    @property
    def terminated(self) -> bool:
        return self._terminated

    async def __call__(self, messages: Sequence["BaseAgentEvent | BaseChatMessage"]) -> StopMessage | None:
        if self._terminated:
            raise TerminatedException("Termination condition has already been reached")
        for m in messages:
            if not isinstance(m, BaseChatMessage):
                continue  # ignore tool-call / internal events
            src = getattr(m, "source", None)
            if src == self._critic:
                self._critic_spoke = True
            elif src == self._finalizer and self._critic_spoke and SENTINEL in m.to_text():
                self._terminated = True
                return StopMessage(
                    content="Finalizer produced FINAL ANSWER after a Critic review.",
                    source="CriticThenFinalize",
                )
        return None

    async def reset(self) -> None:
        self._critic_spoke = False
        self._terminated = False


SELECTOR_PROMPT = """You are coordinating a small team answering one question.

The team members and their roles:
{roles}

Conversation so far:
{history}

Select the SINGLE next member from {participants} to act next.

The members have STRICTLY PARTITIONED capabilities — no member can do another's
job, so the answer almost always requires more than one of them:
- WebResearcher: the ONLY member who can access the web (search + read pages).
- Analyst: the ONLY member who can run code (compute, count, parse, date/number
  reasoning). If the question needs ANY non-trivial calculation or counting, the
  Analyst MUST take a turn — no one else may compute.
- Critic: has NO tools. Reviews the evidence and the proposed answer, says what is
  supported vs. unverified/missing, and delegates gaps. The Critic NEVER finalizes.
- Finalizer: has NO tools. The ONLY member who may output the final answer, and only
  AFTER the Critic has reviewed and its concerns are resolved.

Routing rules:
- Early on, pick WebResearcher to gather facts.
- If a computation, count, or date/number step is needed, pick Analyst — do not let
  another member do the math.
- Once an answer has been proposed, route to the Critic to review it.
- If the Critic raises an issue, route to the member who can address it
  (WebResearcher for facts, Analyst for computation) BEFORE returning to the Critic.
- Only route to the Finalizer once the Critic has reviewed and its concerns are
  resolved. The Finalizer cannot run before the Critic.

Return only the member name."""

RESEARCHER_SYS = (
    "You are WebResearcher on a team answering one question. You are the ONLY "
    "teammate who can access the web — use web_search and fetch_url to gather the "
    "facts the team needs. Investigate thoroughly: run multiple searches and read "
    "the most promising pages before concluding. When done, post ONE concise "
    "message to the team stating exactly what you found and citing the source URLs. "
    "Your teammates CANNOT see your searches or the pages you read — they see only "
    "the message you post, so make it self-contained and include the specific "
    "numbers/values behind your conclusion. Never guess — if a fact cannot be found, "
    "say so plainly. You cannot run code: if a computation is needed, hand the raw "
    "facts to the Analyst. Do not write 'FINAL ANSWER:'; leave finalization to the "
    "Finalizer."
)
ANALYST_SYS = (
    "You are Analyst on a team answering one question. You are the ONLY teammate who "
    "can run code — use run_python for any computation, counting, parsing, or date "
    "arithmetic, and never do nontrivial math in your head. Your teammates cannot "
    "see your code or its output, only the message you post. Given the facts gathered "
    "by the team, compute the required result and post ONE message stating the result "
    "and the key numbers/steps. You cannot access the web: if a fact is missing, say "
    "what you need from the WebResearcher. Do not write 'FINAL ANSWER:'; leave "
    "finalization to the Finalizer."
)
# The Critic owns REVIEW and is structurally barred from finalizing (the termination
# guard ignores any sentinel it writes). Its whole job is the adversarial check that
# a single rubber-stamping Verifier skipped 20/28 times.
CRITIC_SYS = (
    "You are the Critic — the team's reviewer. You have NO tools: you cannot search "
    "the web or run code, and you only see the messages your teammates posted, not "
    "the private work behind them. Your job is to SCRUTINIZE, never to answer.\n\n"
    "Review the proposed answer against the evidence the team actually posted. State "
    "explicitly:\n"
    "- what is SUPPORTED by the posted evidence;\n"
    "- what is UNVERIFIED, internally inconsistent, or MISSING;\n"
    "- anything that looks like a teammate over-claimed beyond what they actually "
    "showed (e.g. asserting a computed result no one computed, or a number with no "
    "cited source).\n"
    "Pay special attention to whether the question's exact constraints were honored "
    "(date ranges, units, 'round up', which segment/subset, etc.) and whether a "
    "required computation was actually run by the Analyst.\n"
    "If anything is wrong or unsupported, say precisely WHAT you need and FROM WHOM "
    "(WebResearcher for facts, Analyst for computation), then STOP so they can address "
    "it. If the answer is fully supported, say so and that it is ready to finalize.\n\n"
    "You are FORBIDDEN to finalize. NEVER write 'FINAL ANSWER:'. Producing the final "
    "answer is the Finalizer's job, not yours."
)
# The Finalizer is the only agent that can end the run, and only after a Critic
# review (enforced by CriticThenFinalize). It must defer to unresolved Critic concerns.
FINALIZER_SYS = (
    "You are the Finalizer. You have NO tools. You act only AFTER the Critic has "
    "reviewed. Read the Critic's review and the evidence the team posted.\n\n"
    "- If the Critic raised any unresolved concern (a missing fact, an uncomputed "
    "result, an unhonored constraint), do NOT finalize: briefly state what still "
    "needs to be done and from whom, then STOP so the team can address it.\n"
    "- Only when the Critic's concerns are resolved and the answer is fully supported "
    "by the posted evidence, output the final answer on its own line in EXACTLY this "
    "format:\n\n"
    "FINAL ANSWER: <answer>\n\n"
    "Match the question's required answer format precisely (a number, a name, or a "
    "short phrase; no extra words, no units unless the gold answer has them)."
)


def make_client(cfg):
    return OpenAIChatCompletionClient(
        model=cfg.get("model", "gpt-4o"),
        base_url=cfg["base_url"],
        api_key=cfg.get("api_key", "dummy"),
    )


async def main() -> None:
    with open("config.yaml") as f:
        cfg = json.load(f)
    with open("prompt.txt") as f:
        prompt = f.read().strip()

    mc = make_client(cfg)

    researcher = TeamAwareAssistantAgent(
        "WebResearcher", model_client=mc, tools=[web_search, fetch_url],
        max_tool_iterations=K, reflect_on_tool_use=True,
        description="Finds facts on the web by searching and reading pages.",
        system_message=RESEARCHER_SYS + TEAM_NOTE,
    )
    analyst = TeamAwareAssistantAgent(
        "Analyst", model_client=mc, tools=[run_python],
        max_tool_iterations=K, reflect_on_tool_use=True,
        description="Computes, counts, parses, and does quantitative reasoning with Python.",
        system_message=ANALYST_SYS + TEAM_NOTE,
    )
    critic = TeamAwareAssistantAgent(
        "Critic", model_client=mc,
        description="Reviews the evidence and proposed answer; flags gaps; never finalizes.",
        system_message=CRITIC_SYS + TEAM_NOTE,
    )
    finalizer = TeamAwareAssistantAgent(
        "Finalizer", model_client=mc,
        description="Emits the final answer, only after the Critic has reviewed.",
        system_message=FINALIZER_SYS + TEAM_NOTE,
    )

    # Structural gate: only a Finalizer sentinel that follows a Critic review ends the run.
    termination = CriticThenFinalize() | MaxMessageTermination(MAX_MESSAGES)
    team = SelectorGroupChat(
        [researcher, analyst, critic, finalizer],
        model_client=mc,
        termination_condition=termination,
        selector_prompt=SELECTOR_PROMPT,
        allow_repeated_speaker=True,
    )

    await Console(team.run_stream(task=prompt))
    await mc.close()


if __name__ == "__main__":
    asyncio.run(main())
