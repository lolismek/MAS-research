"""The arm seam: 7 policies over (edge payload, shared store) — duet's table,
localized to one dialogue edge. An arm decides exactly two things: what crosses
to B, and what is written to / rendered from the one store. `vanilla` must be
byte-identical to a harness with no arm at all (asserted offline).

| arm         | payload to B                          | store                        |
|-------------|---------------------------------------|------------------------------|
| vanilla     | A's wrap-up note                      | —                            |
| full        | note + raw transcript                 | transcript store             |
| sop         | typed note (4 fixed sections)         | —                            |
| down        | note + one B→A follow-up exchange     | — (asks/declines counted)    |
| board       | note + belief ledger                  | ledger, A-written (tools)    |
| extract     | note + belief ledger                  | same ledger, observer-written|
| board_inert | note only                             | ledger written, never rendered|

Sanctioned injection points: A's system suffix (board incentive only), the
wrap-up prompt, arm-owned tool schemas, the edge payload, the post-edge
follow-up. Arms never touch Sam, the quiz, or the probe.
"""
import json

import llm
import prompts
from store import BeliefLedger, parse_typed_lines

OBSERVER_MAX_ENTRIES = 10


def _tool(name, desc, params, required):
    return {"type": "function",
            "function": {"name": name, "description": desc,
                         "parameters": {"type": "object", "properties": params,
                                        "required": required}}}


def _args_dict(arguments):
    if isinstance(arguments, dict):
        return arguments
    try:
        return json.loads(arguments or "{}")
    except Exception:
        return {}


class AddOn:
    """No-op seam == the `vanilla` arm."""

    name = "vanilla"

    def __init__(self):
        self.stats = {}

    def bind(self, usage, seed):
        self.usage, self.seed = usage, seed

    def system_suffix(self, role):
        return ""

    def extra_tool_specs(self, role):
        return []

    def run_extra_tool(self, name, arguments):
        return f"ERROR: no such tool {name!r}"

    def on_turn_end(self, role, text):
        return None

    def wrapup_prompt(self, default):
        return default

    def edge_payload(self, note, transcript):
        """What B reads. `note` is A's wrap-up; `transcript` the full dialogue."""
        return note

    def followup(self, material, ask_b, ask_a):
        """down's hook: may run one bounded B→A exchange; returns an appendix
        string ('' for everyone else). ask_b/ask_a are single-call closures."""
        return ""

    def fidelity_material(self):
        """Store-only render for the ledger-fidelity elicitation (board/extract):
        B answers the quiz from the store ALONE — measures what the memory
        mechanism itself preserved. None when there is no store."""
        return None

    def store_json(self):
        return None


class FullAddOn(AddOn):
    name = "full"

    def edge_payload(self, note, transcript):
        return note + "\n\n" + transcript.render(prompts.TRANSCRIPT_TITLE)

    def store_json(self):
        return None  # transcript already saved as dialogue.txt by run_task


_SOP_HEADERS = ["SITUATION:", "ADVICE GIVEN:", "RATIONALE:", "OPEN QUESTIONS:"]


class SopAddOn(AddOn):
    name = "sop"

    def wrapup_prompt(self, default):
        return prompts.WRAPUP_SOP.format(sam_name=self.seed["sam_name"])

    def edge_payload(self, note, transcript):
        self.stats["sop_conform"] = sum(1 for h in _SOP_HEADERS if h in note.upper())
        return note


class DownAddOn(AddOn):
    name = "down"

    def followup(self, material, ask_b, ask_a):
        reply = ask_b(prompts.B_FOLLOWUP_ASK.format(
            material=material, a_name=self.seed["a_name"]))
        q = ""
        for line in (reply or "").splitlines():
            if line.strip().upper().startswith("QUESTION:"):
                q = line.split(":", 1)[1].strip()
                break
        if not q or q.lower() == "none":
            self.stats["down_declined"] = 1
            return ""
        self.stats["down_asked"] = 1
        self.stats["down_question"] = q
        answer = ask_a(prompts.A_FOLLOWUP.format(question=q))
        return prompts.DOWN_APPENDIX.format(a_name=self.seed["a_name"],
                                            question=q, answer=answer)


class BoardAddOn(AddOn):
    name = "board"

    def __init__(self):
        super().__init__()
        self.ledger = BeliefLedger()

    def system_suffix(self, role):
        return prompts.BOARD_INCENTIVE if role == "A" else ""

    def extra_tool_specs(self, role):
        if role != "A":
            return []
        return [
            _tool("add_belief",
                  "Privately record something you currently believe — a view, "
                  "preference, hunch, or confidence. Returns the note's id.",
                  {"text": {"type": "string"},
                   "confidence": {"type": "number",
                                  "description": "0-1, how strongly you hold it"}},
                  ["text"]),
            _tool("revise_belief", "Update one of your earlier notes by id.",
                  {"id": {"type": "integer"}, "text": {"type": "string"}},
                  ["id", "text"]),
        ]

    def run_extra_tool(self, name, arguments):
        args = _args_dict(arguments)
        if name == "add_belief":
            if not (args.get("text") or "").strip():
                return "ERROR: empty text"
            eid = self.ledger.add("A", args["text"], args.get("confidence"))
            self.stats["board_writes"] = self.stats.get("board_writes", 0) + 1
            return f"noted (id {eid})"
        if name == "revise_belief":
            ok = self.ledger.revise(args.get("id"), args.get("text"))
            if ok:
                self.stats["board_revisions"] = self.stats.get("board_revisions", 0) + 1
            return "revised" if ok else "ERROR: no such id"
        return super().run_extra_tool(name, arguments)

    def _title(self):
        return prompts.BOARD_TITLE.format(a_name=self.seed["a_name"])

    def edge_payload(self, note, transcript):
        board = self.ledger.render(self._title())
        return note + ("\n\n" + board if board else "")

    def fidelity_material(self):
        return self.ledger.render(self._title()) or None

    def store_json(self):
        return self.ledger.as_json()


class BoardInertAddOn(BoardAddOn):
    """Writes happen, nothing rendered — controls for 'does the act of writing
    change what A says out loud' (the leakage-through-verbalization confound)."""

    name = "board_inert"

    def edge_payload(self, note, transcript):
        return note


class ExtractAddOn(AddOn):
    """Same ledger, observer-written: one call at the edge reads the full
    dialogue and reconstructs A's state (duet-faithful: observer fires at edge
    events, no cooperation from A). The observer runs through llm.chat like
    everything else; its cost is on-meter."""

    name = "extract"

    def __init__(self):
        super().__init__()
        self.ledger = BeliefLedger()

    def edge_payload(self, note, transcript):
        sys_p = prompts.OBSERVER_SYS.format(a_name=self.seed["a_name"],
                                            sam_name=self.seed["sam_name"],
                                            max_entries=OBSERVER_MAX_ENTRIES)
        req = prompts.OBSERVER_REQUEST.format(
            transcript=transcript.render(prompts.TRANSCRIPT_TITLE),
            a_name=self.seed["a_name"])
        msg = llm.chat([{"role": "system", "content": sys_p},
                        {"role": "user", "content": req}], tag="observer")
        self.usage.add(msg.get("_usage") or {})
        entries = parse_typed_lines(msg.get("content"))[:OBSERVER_MAX_ENTRIES]
        for e in entries:
            self.ledger.add("observer", e["text"], kind=e["kind"])
        self.stats["observer_entries"] = len(entries)
        board = self.ledger.render(
            prompts.EXTRACT_TITLE.format(a_name=self.seed["a_name"]))
        return note + ("\n\n" + board if board else "")

    def fidelity_material(self):
        return self.ledger.render(
            prompts.EXTRACT_TITLE.format(a_name=self.seed["a_name"])) or None

    def store_json(self):
        return self.ledger.as_json()


ARMS = {cls.name: cls for cls in
        [AddOn, FullAddOn, SopAddOn, DownAddOn, BoardAddOn, BoardInertAddOn,
         ExtractAddOn]}


def make_addon(name):
    return ARMS[name]()
