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

Select the SINGLE next member from {participants} to act next. Guidance:
- WebResearcher: find facts on the web (searches + reading pages).
- Analyst: compute, count, parse, or do date/number reasoning once the needed
  facts are available.
- Verifier: check the proposed answer against the evidence and finalize.
Prefer WebResearcher early (gather facts), Analyst for any computation, and
Verifier to confirm and finalize. Return only the member name."""

RESEARCHER_SYS = (
    "You are WebResearcher on a team answering one question. Use web_search and "
    "fetch_url to gather the facts the team needs. Investigate thoroughly: run "
    "multiple searches and read the most promising pages before concluding. When "
    "done, post ONE concise message to the team stating exactly what you found and "
    "citing the source URLs. Never guess — if a fact cannot be found, say so "
    "plainly. Do not write 'FINAL ANSWER:'; leave finalization to the Verifier."
)
ANALYST_SYS = (
    "You are Analyst on a team answering one question. Use run_python for any "
    "computation, counting, parsing, or date arithmetic — do not do nontrivial "
    "math in your head. Given the facts gathered by the team, compute the required "
    "result and post ONE message stating the result and the key numbers/steps. Do "
    "not write 'FINAL ANSWER:'; leave finalization to the Verifier."
)
VERIFIER_SYS = (
    "You are Verifier, the team's checker and finalizer. Review the team's findings "
    "and reasoning against the evidence. If anything is unverified, inconsistent, or "
    "missing, say what is wrong and let the relevant teammate (WebResearcher or "
    "Analyst) address it on the next turn — you may also use web_search/fetch_url to "
    "double-check facts yourself. Only when you are confident the answer is correct "
    "and fully supported, output the final answer on its own line in EXACTLY this "
    "format:\n\nFINAL ANSWER: <answer>\n\nMatch the question's required answer format "
    "precisely (a number, a name, or a short phrase; no extra words). Do not write "
    "'FINAL ANSWER:' until you are confident."
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
    verifier = AssistantAgent(
        "Verifier", model_client=mc, tools=[web_search, fetch_url],
        max_tool_iterations=K, reflect_on_tool_use=True,
        description="Checks the proposed answer against evidence and finalizes it.",
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
