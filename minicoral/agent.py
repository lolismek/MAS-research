"""AgentRuntime: the generate -> execute-tools -> repeat loop with 32k context
management.

Context policy (plan + paper C.6):
- High-water mark (compact_at_tokens): once crossed, the session is reset at
  the NEXT eval boundary --- [system CORAL.md] + restart orientation (C.6
  5-point block) + the last eval result (heartbeat prompts already appended to
  it by CoralCLI). Compaction-as-session-reset is the paper-sanctioned
  recovery: externalized memory (notes/attempts) is the designed carrier.
- Mid-turn overflow backstop: if context approaches max_context without an
  eval to reset at, the oldest non-system turns are mechanically truncated
  (logged as a compaction event with strategy=truncate).

Stop conditions handled here: stop_event (orchestrator), max_turns.
Dead-agent restart is the orchestrator's job; it builds a fresh runtime with
restart_orientation=True.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .engine import Engine, GenRequest, GenResult
from .hub import Hub
from .prompts import render_restart_orientation
from .tools import TOOL_SCHEMAS, ToolExecutor
from .trajlog import TrajLogger

KICKOFF = "Begin working on the task now. Get oriented first (see Orientation in your instructions)."

NUDGE = (
    "You did not call any tool. Make progress with the tools: edit files, then "
    'run coral eval -m "..." to score your changes.'
)

PARSE_ERROR_TEMPLATE = (
    "Your tool call could not be executed: {error}\n"
    "Emit a valid tool call (see Runtime Tools in your instructions)."
)


class AgentRuntime:
    def __init__(
        self,
        agent_id: str,
        engine: Engine,
        executor: ToolExecutor,
        hub: Hub,
        traj: TrajLogger,
        system_prompt: str,
        *,
        max_turns: int = 200,
        max_context: int = 32768,
        compact_at_tokens: int = 24576,
        max_new_tokens: int = 2048,
        temperature: float = 0.7,
        thinking: bool = False,
        seed: int | None = None,
        score_direction_text: str = "higher is better",
        shared_dir: str = ".coral/public",
        restart_orientation: bool = False,
        transport: Any = None,  # NoteTransport; passed through for wants_capture()
    ):
        self.agent_id = agent_id
        self.engine = engine
        self.executor = executor
        self.hub = hub
        self.traj = traj
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.max_context = max_context
        self.compact_at_tokens = compact_at_tokens
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.thinking = thinking
        self.seed = seed
        self.score_direction_text = score_direction_text
        self.shared_dir = shared_dir
        self.transport = transport

        self.turn = 0
        self.messages: list[dict] = []
        self._pending_compaction = False
        self._start_session(self._initial_user_message(restart_orientation), kind="start")

    # -- session construction ---------------------------------------------------

    def _orientation_block(self) -> str:
        return render_restart_orientation(
            attempt_count=len(self.hub.attempts()),
            own_attempt_count=len([a for a in self.hub.attempts() if a.agent_id == self.agent_id]),
            best_score=self.hub.best_score(),
            own_best_score=self.hub.best_score(self.agent_id),
            score_direction=self.score_direction_text,
            shared_dir=self.shared_dir,
            agent_id=self.agent_id,
        )

    def _initial_user_message(self, restart: bool) -> str:
        if restart:
            return self._orientation_block() + "\n" + KICKOFF
        return KICKOFF

    def _start_session(self, user_message: str, kind: str) -> None:
        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]
        self.traj.log(
            "session_start",
            kind=kind,
            turn=self.turn,
            messages=self.messages,
            gen_params={
                "max_new_tokens": self.max_new_tokens,
                "temperature": self.temperature,
                "thinking": self.thinking,
                "seed": self.seed,
            },
        )

    # -- main loop -----------------------------------------------------------------

    async def run(self, stop_event: asyncio.Event | None = None) -> str:
        """Run until a stop condition; returns the reason."""
        while True:
            if stop_event is not None and stop_event.is_set():
                return "stopped"
            if self.turn >= self.max_turns:
                return "max_turns"
            self.turn += 1
            try:
                await self._one_turn()
            except Exception as e:
                self.traj.log("error", turn=self.turn, error=repr(e))
                raise

    async def _one_turn(self) -> None:
        gen = await self._generate()
        self.messages.append(self._assistant_message(gen))
        self.traj.log(
            "assistant", turn=self.turn, text=gen.text, thinking=gen.thinking,
            tool_calls=[{"id": c.id, "name": c.name, "arguments": c.arguments}
                        for c in gen.tool_calls],
            finish_reason=gen.finish_reason,
            prompt_tokens=gen.prompt_tokens, completion_tokens=gen.completion_tokens,
            parse_errors=[e.error for e in gen.parse_errors],
        )

        eval_result_content: str | None = None
        if gen.tool_calls:
            self.executor.last_gen = gen
            for call in gen.tool_calls:
                self.traj.log("tool_call", turn=self.turn, id=call.id,
                              name=call.name, arguments=call.arguments)
                result = await self.executor.execute(call)
                self.traj.log("tool_result", turn=self.turn, id=call.id,
                              name=call.name, content=result.content,
                              is_error=result.is_error, meta=result.meta)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": result.tool_call_id,
                    "content": result.content,
                })
                if result.meta.get("coral", [None])[0] == "eval" and not result.is_error:
                    eval_result_content = result.content
        elif gen.parse_errors:
            errors = "; ".join(e.error for e in gen.parse_errors)
            self.messages.append({"role": "user",
                                  "content": PARSE_ERROR_TEMPLATE.format(error=errors)})
            self.traj.log("error", turn=self.turn, error=f"parse errors: {errors}")
        else:
            self.messages.append({"role": "user", "content": NUDGE})

        self._manage_context(eval_result_content)

    async def _generate(self) -> GenResult:
        req = GenRequest(
            messages=self.messages,
            tools=TOOL_SCHEMAS,
            max_new_tokens=self.max_new_tokens,
            temperature=self.temperature,
            seed=self.seed,
            enable_thinking=self.thinking,
            capture_states=bool(self.transport and self.transport.wants_capture()),
        )
        return await self.engine.generate(req)

    def _assistant_message(self, gen: GenResult) -> dict:
        msg: dict = {"role": "assistant", "content": gen.text}
        if gen.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                }
                for c in gen.tool_calls
            ]
        return msg

    # -- context management ------------------------------------------------------------

    def _count_tokens(self) -> int:
        return self.engine.count_tokens(self.messages, TOOL_SCHEMAS)

    def _manage_context(self, eval_result_content: str | None) -> None:
        tokens = self._count_tokens()
        if tokens > self.compact_at_tokens:
            self._pending_compaction = True

        if self._pending_compaction and eval_result_content is not None:
            # Session reset at the eval boundary (heartbeats ride in the result).
            before = tokens
            self._start_session(
                self._orientation_block()
                + "\nYour latest eval result:\n" + eval_result_content,
                kind="compaction",
            )
            self._pending_compaction = False
            self.traj.log("compaction", turn=self.turn, strategy="session_reset",
                          tokens_before=before, tokens_after=self._count_tokens())
            return

        # Mid-turn overflow backstop: mechanical truncation of oldest turns.
        hard_limit = self.max_context - self.max_new_tokens
        if tokens > hard_limit:
            before = tokens
            dropped = 0
            while self._count_tokens() > self.compact_at_tokens and len(self.messages) > 3:
                del self.messages[1]
                dropped += 1
                # keep tool results paired with their assistant turn
                while len(self.messages) > 2 and self.messages[1].get("role") == "tool":
                    del self.messages[1]
                    dropped += 1
            self.traj.log("compaction", turn=self.turn, strategy="truncate",
                          dropped_messages=dropped,
                          tokens_before=before, tokens_after=self._count_tokens())
