"""The A↔Sam dialogue — beliefdial's stand-in for A's internal ReAct loop.

Sam opens, then A and Sam alternate for TURNS exchanges (A speaks last). Each
A reply is one 'loop iteration': board-arm tools (add_belief/revise_belief) are
offered on every A call, so writes can happen at every iteration, mirroring
duet's per-iteration producer writes. Sam is FIXED — same prompt, same params,
across every arm (the evidence control).

`Speaker` holds one side's message history; `continue_speaker` appends one user
message and does a single no-tool call — how A is asked for the wrap-up note,
the down follow-up answer, and the private probe, with its full conversational
memory intact (duet's continue_agent pattern).
"""
import os

import llm
import prompts
from store import TranscriptStore

TURNS = int(os.environ.get("BELIEFDIAL_TURNS", "6"))
TOOL_STEPS = 4          # board writes per single reply; a cap, not a target
REPLY_MAX_TOKENS = None  # llm.MAX_OUTPUT_TOKENS (think trace needs the room)

_NUDGE = "Reply with your message now, in plain text."


def _strip_private(msg):
    return {k: v for k, v in msg.items() if not k.startswith("_")}


class Speaker:
    def __init__(self, name, system, usage, tag, addon=None, role=None):
        self.name = name
        self.usage = usage
        self.tag = tag
        self.addon = addon
        self.role = role
        self.messages = [{"role": "system", "content": system}]

    def hear(self, text):
        self.messages.append({"role": "user", "content": text})

    def speak(self):
        """One reply; runs the (optional) arm-tool loop until plain text."""
        specs = self.addon.extra_tool_specs(self.role) if self.addon else []
        msg = None
        for _ in range(TOOL_STEPS + 1):
            msg = llm.chat(self.messages, tools=specs or None,
                           max_tokens=REPLY_MAX_TOKENS, tag=self.tag)
            self.usage.add(msg.get("_usage") or {})
            calls = msg.get("tool_calls") or []
            if not calls:
                break
            self.messages.append(_strip_private(msg))
            for tc in calls:
                fn = tc.get("function") or {}
                result = self.addon.run_extra_tool(fn.get("name"),
                                                   fn.get("arguments"))
                self.messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                                      "content": result})
            specs = self.addon.extra_tool_specs(self.role)
            msg = None          # consumed (already appended with its tool results)
        if msg is None or not llm.usable_text(msg.get("content")):
            # ran out of tool steps, or an empty/sentinel reply: nudge once, no tools
            if msg is not None:
                self.messages.append({"role": "assistant",
                                      "content": (msg.get("content") or "").strip() or "..."})
            self.hear(_NUDGE)
            msg = llm.chat(self.messages, max_tokens=REPLY_MAX_TOKENS, tag=self.tag)
            self.usage.add(msg.get("_usage") or {})
        text = (msg.get("content") or "").strip() or "..."
        self.messages.append({"role": "assistant", "content": text})
        return text


def continue_speaker(speaker, user_text, tag=None):
    """One extra no-tool turn on a finished speaker (wrap-up / probe / follow-up)."""
    speaker.hear(user_text)
    msg = llm.chat(speaker.messages, tag=tag or speaker.tag)
    speaker.usage.add(msg.get("_usage") or {})
    text = (msg.get("content") or "").strip()
    if not llm.usable_text(text):
        speaker.messages.append({"role": "assistant", "content": text or "..."})
        speaker.hear(_NUDGE)
        msg = llm.chat(speaker.messages, tag=tag or speaker.tag)
        speaker.usage.add(msg.get("_usage") or {})
        text = (msg.get("content") or "").strip()
    speaker.messages.append({"role": "assistant", "content": text})
    return text


def run_dialogue(seed, addon, usage, turns=None):
    """Returns (transcript: TranscriptStore, a: Speaker) — A kept alive for
    the wrap-up, the down follow-up, and the manipulation probe."""
    turns = turns or TURNS
    a = Speaker(seed["a_name"], prompts.a_system(seed) + addon.system_suffix("A"),
                usage, tag="A", addon=addon, role="A")
    sam = Speaker(seed["sam_name"], prompts.sam_system(seed), usage, tag="Sam")
    transcript = TranscriptStore()

    sam.hear(prompts.SAM_OPEN.format(a_name=seed["a_name"]))
    sam_text = sam.speak()
    transcript.add(seed["sam_name"], sam_text)

    for i in range(turns):
        a.hear(sam_text)
        a_text = a.speak()
        transcript.add(seed["a_name"], a_text)
        addon.on_turn_end("A", a_text)
        if i == turns - 1:
            break
        sam.hear(a_text)
        sam_text = sam.speak()
        transcript.add(seed["sam_name"], sam_text)
    return transcript, a
