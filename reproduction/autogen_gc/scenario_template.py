"""AutoGen SelectorGroupChat scenario for ONE GAIA task (second MAS baseline).

Topology contrast vs. Magentic-One (a star with one reasoning orchestrator):
here three PEER agents coordinate through a shared transcript, and each agent
does deep work PRIVATELY before publishing one message.

Each role is an ``AssistantAgent(max_tool_iterations=K)`` — within a single turn
it runs an internal ReAct loop (model -> tool -> model -> ... up to K) whose tool
calls/results live in private ``inner_messages``; it then publishes exactly ONE
``chat_message`` to the group. Peers see only that message. The gap between an
agent's rich hidden state and its lossy published digest is the only place
inter-agent misalignment (MAST 2.4 distortion, 2.5 ignored-input, ToM) can arise
— the property Magentic-One's star lacks.

The selector (an LLM) routes between WebResearcher / Analyst / Verifier. The
Verifier owns finalization: it emits "FINAL ANSWER: <x>" once satisfied, which
the run harness greps (same sentinel as the Magentic harness) and which
terminates the chat.

Copied verbatim into each run dir by run_task.py; reads config.yaml + prompt.txt
from the cwd. ``tools`` is importable because run_task.py puts
reproduction/autogen_gc on PYTHONPATH.
"""
import asyncio
import json
import os

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

from tools import web_search, fetch_url, run_python

K = int(os.environ.get("MAX_TOOL_ITERATIONS", "8"))      # internal ReAct depth per turn
MAX_MESSAGES = int(os.environ.get("MAX_MESSAGES", "30"))  # outer-chat message cap

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
  reasoning). If the question needs ANY non-trivial calculation or counting,
  the Analyst MUST take a turn — no one else may compute.
- Verifier: has NO tools. It reviews the proposed answer against the evidence and
  is the only member that may finalize.

Routing rules:
- Early on, pick WebResearcher to gather facts.
- If a computation, count, or date/number step is needed, pick Analyst — do not
  let another member do the math.
- After an answer has been proposed, route to Verifier to review it.
- The Verifier must review at least once before any answer is finalized. If the
  Verifier raises an issue or asks for something, route to the member who can
  address it (WebResearcher for facts, Analyst for computation) BEFORE returning
  to the Verifier to finalize.

Return only the member name."""

RESEARCHER_SYS = (
    "You are WebResearcher on a team answering one question. You are the ONLY "
    "teammate who can access the web — use web_search and fetch_url to gather the "
    "facts the team needs. Investigate thoroughly: run multiple searches and read "
    "the most promising pages before concluding. When done, post ONE concise "
    "message to the team stating exactly what you found and citing the source URLs. "
    "Your teammates CANNOT see your searches or the pages you read — they see only "
    "the message you post, so make it self-contained. Never guess — if a fact "
    "cannot be found, say so plainly. You cannot run code: if a computation is "
    "needed, hand the raw facts to the Analyst. Do not write 'FINAL ANSWER:'; leave "
    "finalization to the Verifier."
)
ANALYST_SYS = (
    "You are Analyst on a team answering one question. You are the ONLY teammate who "
    "can run code — use run_python for any computation, counting, parsing, or date "
    "arithmetic, and never do nontrivial math in your head. Your teammates cannot "
    "see your code or its output, only the message you post. Given the facts "
    "gathered by the team, compute the required result and post ONE message stating "
    "the result and the key numbers/steps. You cannot access the web: if a fact is "
    "missing, say what you need from the WebResearcher. Do not write 'FINAL "
    "ANSWER:'; leave finalization to the Verifier."
)
# Two-phase, tool-less Verifier: it has NO tools, so it cannot silently re-do the
# others' work — it must rely on their published digests and delegate gaps back to
# them. It separates REVIEW (an explicit critique turn) from FINALIZE (emitting the
# sentinel on a later turn), which forces at least one genuine verification turn and
# is where ignored-input (2.5) / accepted-distortion (2.4) become observable.
VERIFIER_SYS = (
    "You are Verifier, the team's checker and finalizer. You have NO tools: you "
    "cannot search the web or run code, so you must reason over what your teammates "
    "have reported — and you only see the messages they posted, not the work behind "
    "them. Work in two phases.\n\n"
    "PHASE 1 — REVIEW (do this first, and do NOT finalize yet): scrutinize the "
    "proposed answer against the evidence the team posted. State explicitly what is "
    "supported, and call out anything unverified, internally inconsistent, missing, "
    "or that looks like a teammate over-claimed beyond what they actually showed. If "
    "anything is wrong or unsupported, say precisely what you need and from whom "
    "(WebResearcher for facts, Analyst for computation), then STOP so they can "
    "address it. Do NOT write 'FINAL ANSWER:' on a review turn.\n\n"
    "PHASE 2 — FINALIZE (only on a later turn, once the team has resolved your "
    "concerns and you are confident the answer is correct and fully supported): "
    "output the final answer on its own line in EXACTLY this format:\n\n"
    "FINAL ANSWER: <answer>\n\n"
    "Match the question's required answer format precisely (a number, a name, or a "
    "short phrase; no extra words). Never finalize on the same turn you first review "
    "a freshly proposed answer."
)


def make_client(cfg):
    # model name "gpt-4o" is a recognized family, so model_info (vision+tools)
    # is auto-populated; the proxy aliases the call to gpt-5.4-mini downstream.
    return OpenAIChatCompletionClient(
        model=cfg.get("model", "gpt-4o"),
        base_url=cfg["base_url"],
        api_key=cfg.get("api_key", "dummy"),
    )


async def main() -> None:
    with open("config.yaml") as f:
        cfg = json.load(f)  # written as JSON by run_task.py (valid YAML too)
    with open("prompt.txt") as f:
        prompt = f.read().strip()

    mc = make_client(cfg)

    researcher = AssistantAgent(
        "WebResearcher", model_client=mc, tools=[web_search, fetch_url],
        max_tool_iterations=K, reflect_on_tool_use=True,
        description="Finds facts on the web by searching and reading pages.",
        system_message=RESEARCHER_SYS,
    )
    analyst = AssistantAgent(
        "Analyst", model_client=mc, tools=[run_python],
        max_tool_iterations=K, reflect_on_tool_use=True,
        description="Computes, counts, parses, and does quantitative reasoning with Python.",
        system_message=ANALYST_SYS,
    )
    # Verifier has NO tools (capability partition): it cannot search or compute, so
    # it must rely on the others' published digests and delegate gaps back to them.
    verifier = AssistantAgent(
        "Verifier", model_client=mc,
        description="Reviews the proposed answer against the evidence and finalizes "
                    "it. Has no tools; relies on the team's reports.",
        system_message=VERIFIER_SYS,
    )

    termination = TextMentionTermination("FINAL ANSWER:") | MaxMessageTermination(MAX_MESSAGES)
    team = SelectorGroupChat(
        [researcher, analyst, verifier],
        model_client=mc,
        termination_condition=termination,
        selector_prompt=SELECTOR_PROMPT,
        allow_repeated_speaker=True,
    )

    await Console(team.run_stream(task=prompt))
    await mc.close()


if __name__ == "__main__":
    asyncio.run(main())
