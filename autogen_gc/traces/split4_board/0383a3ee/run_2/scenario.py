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

from board import Board, BoardInjectingContext
from tools import web_search, fetch_url, run_python, make_board_tools

K = int(os.environ.get("MAX_TOOL_ITERATIONS", "8"))       # internal ReAct depth per turn
MAX_MESSAGES = int(os.environ.get("MAX_MESSAGES", "30"))   # outer-chat message cap
SENTINEL = "FINAL ANSWER:"

# Shared "thinking memory" board — OFF by default. When off, none of the board code
# below is constructed and the run is behaviorally identical to the baseline.
SHARED_MEMORY = os.environ.get("SHARED_MEMORY", "0") == "1"
SELECTOR_BOARD = os.environ.get("SELECTOR_BOARD", "1") == "1"   # only meaningful if SHARED_MEMORY
K_NOTE = int(os.environ.get("BOARD_NOTE_ITERS", "3"))          # tool-loop budget for the no-web/code agents


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
        # Bump the board's per-turn logical clock exactly once per agent turn (when new
        # teammate/user messages arrive). No-op unless this is a BoardInjectingContext.
        board = getattr(model_context, "_board", None)
        if board is not None and messages:
            board.mark_turn()
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

# Board-mode selector prompt. Adds a {board} block (filled with the rendered scratchpad
# at selection time) and asks for a one-line rationale BEFORE the name. The rationale is
# captured and written back to the board so the chosen agent sees WHY it was picked.
# Used only when SHARED_MEMORY and SELECTOR_BOARD; {board} is always substituted (with
# "" when the board is empty) so str.format never sees a stray placeholder.
SELECTOR_PROMPT_BOARD = """You are coordinating a small team answering one question.

The team members and their roles:
{roles}

Conversation so far:
{history}

{board}

Select the SINGLE next member from {participants} to act next.

The members have STRICTLY PARTITIONED capabilities — no member can do another's
job, so the answer almost always requires more than one of them:
- WebResearcher: the ONLY member who can access the web (search + read pages).
- Analyst: the ONLY member who can run code (compute, count, parse, date/number
  reasoning). If the question needs ANY non-trivial calculation or counting, the
  Analyst MUST take a turn — no one else may compute.
- Critic: has no web/code tools (only the shared scratchpad). Reviews the evidence and
  the proposed answer, says what is supported vs. unverified/missing, and delegates
  gaps. The Critic NEVER finalizes.
- Finalizer: has no web/code tools (only the shared scratchpad). The ONLY member who
  may output the final answer, and only AFTER the Critic has reviewed and its concerns
  are resolved.

Routing rules:
- Early on, pick WebResearcher to gather facts.
- If a computation, count, or date/number step is needed, pick Analyst — do not let
  another member do the math.
- Once an answer has been proposed, route to the Critic to review it.
- If the Critic raises an issue, route to the member who can address it
  (WebResearcher for facts, Analyst for computation) BEFORE returning to the Critic.
- Only route to the Finalizer once the Critic has reviewed and its concerns are
  resolved. The Finalizer cannot run before the Critic.

First, write ONE short sentence explaining your choice (you may reference the
scratchpad and teammates). Then, on a NEW FINAL LINE, output ONLY the chosen member's
name and nothing else."""

# Appended to every agent's system message in board mode (the suggestions are exactly
# that — suggestions; the scratchpad is intentionally open-ended).
BOARD_NOTE = (
    "\n\nSHARED SCRATCHPAD: you and your teammates share a scratchpad of free-form "
    "notes, shown near the top of your context. Use add_note to record what you now "
    "believe, what you tried that failed, or what you're stuck on, AS YOU WORK, so "
    "teammates can build on your reasoning. APPEND a new note whenever you learn or "
    "decide something; use revise_note ONLY to fix one of YOUR earlier notes that "
    "turned out FALSE — older notes stay visible on purpose. Read teammates' notes "
    "before acting. The scratchpad does NOT replace your posted message; still post "
    "your findings to the team as usual."
)

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
    "- If the Critic raised an unresolved concern that the team can still realistically "
    "act on (a fact not yet searched, a computation not yet run), do NOT finalize: "
    "briefly state what is needed and from whom, then STOP so the team can address it.\n"
    "- When the Critic's concerns are resolved and the answer is fully supported by the "
    "posted evidence, output the final answer (format below).\n\n"
    "STALL / GIVE-UP RULE — this OVERRIDES the 'do not finalize' rule above. The run "
    "will loop forever if you keep deferring on a concern the team cannot satisfy. You "
    "MUST recognize a stall and finalize anyway when ANY of these hold:\n"
    "  * the team has already been asked for the SAME missing item and has reported it "
    "unobtainable / not found two or more times;\n"
    "  * the recent messages are repeating with no NEW evidence or progress;\n"
    "  * the Critic is demanding evidence that the available tools cannot produce "
    "(e.g. a specific source's raw historical data that only renders in a browser).\n"
    "In any of those cases, do NOT defer again. Finalize NOW with the best-supported "
    "answer the posted evidence allows. If the evidence genuinely supports no defensible "
    "answer, output 'FINAL ANSWER: cannot be determined'. A timely best-effort answer "
    "(or an explicit 'cannot be determined') is ALWAYS better than another deferral.\n\n"
    "Final answer format — output it on its own line EXACTLY as:\n\n"
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


def _make_board_selector_team(agents, board, mc, termination):
    """Build a SelectorGroupChat whose manager (a) splices the rendered board into the
    selector prompt and (b) writes its one-line routing rationale back to the board, so
    the chosen agent sees WHY it was picked.

    This reaches into a private AutoGen class (SelectorGroupChatManager) and re-creates a
    version-specific factory, so the caller MUST wrap it in try/except and fall back to a
    stock SelectorGroupChat. The eager factory probe at the end forces a signature drift
    (e.g. a future AutoGen bump) to raise HERE — where the caller can fall back — rather
    than deep inside run_stream. Verified against autogen-agentchat 0.7.5.
    """
    from autogen_agentchat.teams._group_chat._selector_group_chat import SelectorGroupChatManager
    from autogen_agentchat.messages import MessageFactory

    class BoardSelectorGroupChatManager(SelectorGroupChatManager):
        def __init__(self, *args, board=None, **kwargs):
            super().__init__(*args, **kwargs)
            self._board = board
            self._last_rationale = ""

        def _mentioned_agents(self, message_content, agent_names):
            # Board mode elicits "<rationale>\n<NAME on the final line>". Parse ONLY the
            # last non-empty line for the name (so a rationale mentioning other agents'
            # names can't trip the >1-mention retry) and stash the rest as the rationale.
            lines = [ln for ln in (message_content or "").splitlines() if ln.strip()]
            if not lines:
                self._last_rationale = ""
                return super()._mentioned_agents(message_content, agent_names)
            self._last_rationale = "\n".join(lines[:-1]).strip()
            return super()._mentioned_agents(lines[-1], agent_names)

        async def _select_speaker(self, roles, participants, max_attempts):
            rendered = self._board.render(for_selector=True) if self._board is not None else ""
            safe = rendered.replace("{", "{{").replace("}", "}}") if rendered else ""
            original = self._selector_prompt
            self._selector_prompt = original.replace("{board}", safe)
            try:
                return await super()._select_speaker(roles, participants, max_attempts)
            finally:
                self._selector_prompt = original

        async def select_speaker(self, thread):
            self._last_rationale = ""
            result = await super().select_speaker(thread)
            if self._board is not None:
                name = result[0] if isinstance(result, list) else result
                rationale = (self._last_rationale or "").strip()
                if rationale:
                    self._board.add_note("Selector", f"(chose {name}) {rationale}")
            return result

    class BoardSelectorGroupChat(SelectorGroupChat):
        def __init__(self, *args, board=None, **kwargs):
            self._board_obj = board
            super().__init__(*args, **kwargs)

        def _create_group_chat_manager_factory(
            self, name, group_topic_type, output_topic_type, participant_topic_types,
            participant_names, participant_descriptions, output_message_queue,
            termination_condition, max_turns, message_factory,
        ):
            board = self._board_obj
            def factory():
                return BoardSelectorGroupChatManager(
                    name, group_topic_type, output_topic_type, participant_topic_types,
                    participant_names, participant_descriptions, output_message_queue,
                    termination_condition, max_turns, message_factory,
                    self._model_client, self._selector_prompt, self._allow_repeated_speaker,
                    self._selector_func, self._max_selector_attempts, self._candidate_func,
                    self._emit_team_events, self._model_context, self._model_client_streaming,
                    board=board,
                )
            return factory

    team = BoardSelectorGroupChat(
        agents, model_client=mc, termination_condition=termination,
        selector_prompt=SELECTOR_PROMPT_BOARD, allow_repeated_speaker=False, board=board,
    )

    # Eager probe: build the manager once via the private factory so a signature drift
    # raises here (caught by the caller) instead of inside run_stream.
    names = [a.name for a in agents]
    _probe = team._create_group_chat_manager_factory(
        name="probe", group_topic_type="probe_g", output_topic_type="probe_o",
        participant_topic_types=list(names), participant_names=list(names),
        participant_descriptions=[getattr(a, "description", "") for a in agents],
        output_message_queue=asyncio.Queue(), termination_condition=None,
        max_turns=None, message_factory=MessageFactory(),
    )
    _probe()  # instantiate once and discard; just validates the factory signature
    return team


async def main() -> None:
    with open("config.yaml") as f:
        cfg = json.load(f)
    with open("prompt.txt") as f:
        prompt = f.read().strip()

    mc = make_client(cfg)

    # Shared board (None when off). All board wiring below degrades to baseline when
    # board is None: empty tool lists, model_context=None (the AssistantAgent default),
    # and no BOARD_NOTE appended — so an OFF run behaves exactly like the baseline.
    board = Board() if SHARED_MEMORY else None

    def _board_ctx():
        return BoardInjectingContext(board) if board is not None else None  # fresh per agent

    def _board_tools(name):
        return make_board_tools(name, board) if board is not None else []

    def _sys(base):
        return base + TEAM_NOTE + (BOARD_NOTE if board is not None else "")

    researcher = TeamAwareAssistantAgent(
        "WebResearcher", model_client=mc,
        tools=[web_search, fetch_url, *_board_tools("WebResearcher")],
        max_tool_iterations=K, reflect_on_tool_use=True,
        description="Finds facts on the web by searching and reading pages.",
        system_message=_sys(RESEARCHER_SYS), model_context=_board_ctx(),
    )
    analyst = TeamAwareAssistantAgent(
        "Analyst", model_client=mc,
        tools=[run_python, *_board_tools("Analyst")],
        max_tool_iterations=K, reflect_on_tool_use=True,
        description="Computes, counts, parses, and does quantitative reasoning with Python.",
        system_message=_sys(ANALYST_SYS), model_context=_board_ctx(),
    )
    # Critic & Finalizer have no web/code tools. In board mode they gain ONLY the
    # scratchpad write-tools (with a small tool-loop budget so they write-then-speak);
    # off, they are built exactly as before (no tools, no model_context) so the baseline
    # is unchanged.
    critic_kwargs = dict(
        model_client=mc,
        description="Reviews the evidence and proposed answer; flags gaps; never finalizes.",
        system_message=_sys(CRITIC_SYS),
    )
    finalizer_kwargs = dict(
        model_client=mc,
        description="Emits the final answer, only after the Critic has reviewed.",
        system_message=_sys(FINALIZER_SYS),
    )
    if board is not None:
        critic_kwargs.update(tools=make_board_tools("Critic", board), max_tool_iterations=K_NOTE,
                             reflect_on_tool_use=True, model_context=_board_ctx())
        finalizer_kwargs.update(tools=make_board_tools("Finalizer", board), max_tool_iterations=K_NOTE,
                                reflect_on_tool_use=True, model_context=_board_ctx())
    critic = TeamAwareAssistantAgent("Critic", **critic_kwargs)
    finalizer = TeamAwareAssistantAgent("Finalizer", **finalizer_kwargs)

    # Structural gate: only a Finalizer sentinel that follows a Critic review ends the run.
    termination = CriticThenFinalize() | MaxMessageTermination(MAX_MESSAGES)
    agents = [researcher, analyst, critic, finalizer]

    def stock_team():
        return SelectorGroupChat(
            agents,
            model_client=mc,
            termination_condition=termination,
            selector_prompt=SELECTOR_PROMPT,
            # AutoGen's default. Each agent does its deep work in ONE turn (internal ReAct
            # loop) and publishes once, so a CONSECUTIVE repeat adds nothing and is the
            # shape of the structural-stall loops (e.g. 08cae58d: WebResearcher picked 8x
            # in a row). Forcing rotation preserves legitimate re-speaking (WR->Critic->WR
            # is non-consecutive) while killing the degenerate same-speaker grind.
            allow_repeated_speaker=False,
        )

    if board is not None and SELECTOR_BOARD:
        try:
            team = _make_board_selector_team(agents, board, mc, termination)
        except Exception as e:  # the selector hook is the one version-fragile piece
            print(f"[board] selector hook unavailable ({e!r}); using stock selector "
                  f"(agents still read/write the board)", flush=True)
            team = stock_team()
    else:
        team = stock_team()

    try:
        await Console(team.run_stream(task=prompt))
    finally:
        # Persist the board even if the run raised, so a crashed/partial run still
        # leaves its belief-evolution trace for debugging and analysis.
        if board is not None:
            with open("board_trace.jsonl", "w") as f:
                f.write(board.dump_events_jsonl())
    await mc.close()


if __name__ == "__main__":
    asyncio.run(main())
