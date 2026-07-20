"""The arm seam, ported from duet to the offline-artifact regime (plan sec. 7).

Here an arm is a pure function over cached data:
    build_artifact(arm, frozen, instance) -> artifact text (or None for floor)
computed OFFLINE from A's frozen phase-1 trajectory — no environment, at most
one or two LLM calls (the note-writing continuation, extract's observer,
down's asker/answerer). All artifacts are precomputed and cached under
artifacts/<instance>/<family_k>/<arm>.txt before any phase-2 spend.

| condition   | artifact                                            | family |
|-------------|-----------------------------------------------------|--------|
| floor       | none (B gets only the task)                         | plain  |
| ceiling     | A's full rendered transcript (no W budget)          | plain  |
| oracle      | gold-templated note (localization + fix diff), <= W | (gold) |
| vanilla     | A's own free-form note (continuation), <= W         | plain  |
| sop         | typed FINDINGS/EVIDENCE/VERDICT/NEXT_STEPS, <= W    | plain  |
| down        | vanilla note + ONE consumer question -> A's answer  | plain  |
| extract     | observer-built belief ledger from A's log, <= W     | plain  |
| board       | A's own in-loop belief ledger, rendered, <= W       | board  |
| board_inert | free-form note from the board-family trajectory     | board  |

board vs board_inert isolates the LEDGER CONTENT channel while matching
A-side tool effects (both phase-1 runs had the write tools); board_inert vs
vanilla isolates the tools' side effect on A itself (duet's confound logic,
adapted: with a fresh-B consumer there is nothing to "not render" to, so the
inert control moves to the artifact side).

Budget: W_SOFT ~300 tokens asked in the prompt; W_HARD enforced by hard
truncation (chars/4 heuristic — no tokenizer dependency). ceiling is exempt
(it IS the no-budget bracket).
"""
import difflib
import json
import re

from harness import instances as I
from harness import llm
from harness.ledger import BeliefLedger, parse_belief_lines

W_SOFT_TOKENS = 300
W_HARD_TOKENS = 500
W_HARD_CHARS = W_HARD_TOKENS * 4
CEILING_CHARS = 12000            # duet's TRANSCRIPT_TOTAL_CHARS
TOOL_RESULT_CHARS = 700          # duet's TRANSCRIPT_TOOL_CHARS

ARMS = ["floor", "ceiling", "oracle", "vanilla", "full", "sop", "down",
        "extract", "board", "board_inert"]
BOARD_FAMILY = {"board", "board_inert"}

# --- prompts (duet's, lightly adapted to the single-handoff setting) ----------
HANDOFF_REQUEST = (
    "You have reached the end of your available time on this task, so you must stop "
    "working now — there is no more time to investigate and no tools are available to you "
    "for this message. Another worker will continue from where you left off. They will NOT "
    "see any of your work above — only the note you write now. Write a concise hand-off "
    "note (aim for at most {soft} tokens), as plain text, covering: what you have "
    "established (with the evidence for it), what is still open or uncertain, and what "
    "you would try next. Do not call any tools — just write the note."
)

SOP_HANDOFF_REQUEST = (
    "You have reached the end of your available time on this task, so you must stop "
    "working now — no tools are available to you for this message. Another worker will "
    "continue from where you left off. They will NOT see any of your work above — only "
    "the structured note you write now (aim for at most {soft} tokens total). Write it "
    "as plain text lines in exactly this form (keep each field on its own line; be "
    "concrete):\n"
    "FINDINGS: <what you have established so far, and how>\n"
    "EVIDENCE: <the key evidence behind those findings>\n"
    "VERDICT: <your current diagnosis of the failure, or UNKNOWN>\n"
    "NEXT_STEPS: <what you would try next>\n"
    "Do not call any tools — just those fields."
)

WRAPUP_NUDGE = (
    "You did not write any text. There are no tools available now and no time left to "
    "investigate further. Respond with plain text only, providing exactly what the "
    "previous message asked for."
)

CHALLENGE_ASK_SYS = (
    "You are about to take over the task given below from a colleague whose note "
    "follows. Before you start, you may ask them ONE question. If anything in it is "
    "unclear, looks unverified, or you are not sure you can rely on it, ask the single "
    "question that would most help you trust or correct it — do not hold back. Output one "
    "line in exactly this form and nothing else:\n"
    "QUESTION: <your one question>\n"
    "If the note is clear and you genuinely have nothing to ask, output exactly:\n"
    "QUESTION: none"
)

CHALLENGE_ANSWER_REQUEST = (
    "The worker taking over asked you one question about your note:\n"
    "{question}\n"
    "Answer it in a short plain-text paragraph from what you actually observed — no "
    "tools are available and there is no time to investigate further. If you do not "
    "know, say so plainly."
)

DOWN_EXCHANGE_TEMPLATE = (
    "{note}\n\n"
    "[clarifying question from the worker taking over]\n{question}\n"
    "[answer from the note's author]\n{answer}"
)

OBSERVER_SYS = (
    "You are reading the working log of an agent that just finished a stretch of work on "
    "a task, so what it now holds can be passed to the next worker — who will NOT see this "
    "log. Surface, from its reasoning and actions, what it takes to be true. Work in two "
    "steps (think it through first):\n"
    "1. Decide which OBJECTS it holds a view on that is worth passing on. Include: (a) "
    "concrete task objects its work is informative about — a specific file, function, "
    "error cause, code fact, or sub-result it found or ruled out (these are OBSERVATIONS "
    "— what it now knows, like memory); and (b) these preset ABSTRACT objects WHEN its "
    "work bears on them: whether the task still seems SOLVABLE, and how far it TRUSTS its "
    "own current diagnosis or planned next step (these are BELIEFS — its subjective "
    "stance). Omit any object the log says nothing about; do not solve the task yourself "
    "and do not invent views the log does not support.\n"
    "2. Output one line per object, most important first, each in EXACTLY one of these two "
    "forms and nothing else:\n"
    "OBSERVATION: <object> | <the concrete thing it found, one claim> | <confidence 0 to 1>\n"
    "BELIEF: <object> | <its subjective view, one sentence> | <confidence 0 to 1>\n"
    "Emit at most {max_beliefs} lines. If the log establishes nothing, output exactly: "
    "BELIEF: none"
)

OBSERVER_REQUEST = (
    "Here is the agent's working log for this stretch:\n\n"
    "<working_log>\n{log}\n</working_log>\n\n"
    "Extract the OBSERVATION / BELIEF lines now."
)

OBSERVER_MAX_BELIEFS = 8

_SOP_FIELDS = ("FINDINGS", "EVIDENCE", "VERDICT", "NEXT_STEPS")
_SOP_HEADER = re.compile(r"^\s*(FINDINGS|EVIDENCE|VERDICT|NEXT_?STEPS)\s*:\s*", re.I | re.M)

# --- board family: A-side write tools + incentive (duet's, single-successor) --
BOARD_WRITE_INCENTIVE = (
    "\n\nSHARED BELIEF BOARD: you and the worker who takes over after you share a belief "
    "board — a running record of what you currently believe, have found, computed, or "
    "ruled out. Your successor never sees your tool calls or your working — so the board "
    "is the only way your intermediate findings reach them. Record beliefs AS YOU WORK, "
    "generously: call add_belief whenever you establish a fact, find a cause (record the "
    "ACTUAL file/function/error), form or rule out a hypothesis, or hit a dead end. Do "
    "not wait until you are finished. Do not repeat a belief already on the board; if one "
    "of YOUR beliefs turns out to be FALSE, fix it with revise_belief. Write to the board "
    "ONLY by calling add_belief / revise_belief — never by typing beliefs into your reply."
)

ADD_BELIEF_SPEC = dict(type="function", function=dict(
    name="add_belief",
    description=(
        "Add one belief to the shared board your successor on this task will see. Use it "
        "GENEROUSLY, as you work — whenever you establish a fact, find a cause (record "
        "the ACTUAL file/function/error), form or rule out a hypothesis, or hit a dead "
        "end. Give the OBJECT (the thing the belief is about), the BELIEF itself (one "
        "concrete claim), and your CONFIDENCE from 0 to 1. Don't wait until you are "
        "finished."),
    parameters=dict(type="object", properties=dict(
        object=dict(type="string", description="the thing the belief is about"),
        belief=dict(type="string", description="one concrete claim about it"),
        confidence=dict(type="number", description="how confident you are, 0 to 1"),
    ), required=["object", "belief", "confidence"])))

REVISE_BELIEF_SPEC = dict(type="function", function=dict(
    name="revise_belief",
    description=(
        "Revise or retract one belief already on the shared board, by its id. Give the "
        "corrected belief text (or status 'retracted') and your confidence. Use it when "
        "evidence shows a recorded belief is wrong or needs sharpening."),
    parameters=dict(type="object", properties=dict(
        belief_id=dict(type="string", description="the id of the belief to revise, e.g. 'b3'"),
        belief=dict(type="string", description="the corrected claim (omit if retracting)"),
        confidence=dict(type="number", description="your confidence in the correction, 0 to 1"),
        status=dict(type="string", description="'retracted' to retract instead of revise"),
    ), required=["belief_id"])))


BOARD_WRAPUP_REQUEST = (
    "Your shift has ended — no more investigation is possible and the repository tools "
    "are gone. Before you leave, bring the shared belief board up to date for your "
    "successor: call add_belief for each concrete thing you now believe that is not yet "
    "on the board (facts you established, the cause as far as you understand it, "
    "hypotheses you ruled out, what you would try next), and revise_belief for any "
    "recorded belief you no longer hold. Only the board reaches your successor. Do not "
    "write prose — only tool calls."
)


def board_wrapup(events, ledger, iid, rounds=2):
    """One (or two) final board-only calls after the budget cut: the ledger
    write-window at shift end. Deviation from duet noted in the module doc:
    with k this small, in-loop adoption alone leaves empty boards (duet/camel
    both observed low write adoption on short stretches), which would test
    'do agents write unprompted' instead of 'does a revisable ledger
    transmit'. In-loop writing (and revision) is still live during the shift."""
    specs, handler = make_board_tools(ledger)
    messages = events_to_messages(events) + [
        {"role": "user", "content": BOARD_WRAPUP_REQUEST}]
    nudged = False
    for r in range(rounds + 1):
        msg = llm.chat(messages, tools=specs, tag=f"arm:board:wrapup{r}:{iid}")
        tcs = msg.get("tool_calls") or []
        if not tcs:
            if nudged or ledger.entries:
                break
            # prose/think instead of tool calls — insist once (think-leak guard)
            nudged = True
            messages += [{"role": "assistant", "content": msg.get("content") or ""},
                         {"role": "user", "content":
                          "You wrote prose, but only the board reaches your successor. "
                          "Respond ONLY with add_belief tool calls recording your "
                          "current beliefs — no text."}]
            continue
        amsg = {"role": "assistant", "content": msg.get("content") or None,
                "tool_calls": tcs}
        messages.append(amsg)
        for tc in tcs:
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": handler(tc["function"]["name"], args)})
    return ledger


def make_board_tools(ledger, author="predecessor"):
    """(specs, handler) for run_agent's extra_tools — the board family's A-side."""
    def handler(name, a):
        if name == "add_belief":
            e = ledger.add(author, a.get("object"), a.get("belief"), a.get("confidence"))
            if not e["belief"]:
                return "ERROR: add_belief needs a non-empty 'belief'."
            return (f"Recorded {e['id']}: {e['object']}: {e['belief']} "
                    f"(confidence {e['confidence']:.2f})")
        if name == "revise_belief":
            e = ledger.revise(author, a.get("belief_id"), belief=a.get("belief"),
                              confidence=a.get("confidence"), status=a.get("status"))
            if e is None:
                have = ", ".join(x["id"] for x in ledger.active()) or "(board empty)"
                return f"ERROR: no belief with id {a.get('belief_id')!r}. Active ids: {have}"
            verb = "Retracted" if e["status"] == "retracted" else "Revised into"
            return f"{verb} {e['id']}: {e['object']}: {e['belief']}"
        return f"ERROR: no such tool {name!r}"
    return [ADD_BELIEF_SPEC, REVISE_BELIEF_SPEC], handler


# --- trajectory plumbing ------------------------------------------------------
def events_to_messages(events):
    """Reconstruct the OpenAI message list from a frozen trajectory so A can be
    'continued' with its working memory intact (duet's continue_agent trick).
    Synthetic tool_call ids; assistant tool_calls without an executed tool
    event (budget cut mid-batch) get a placeholder result."""
    messages, i, tc_id = [], 0, 0
    events = list(events)
    while i < len(events):
        ev = events[i]
        if ev["type"] == "system":
            messages.append({"role": "system", "content": ev["content"]})
        elif ev["type"] == "user":
            messages.append({"role": "user", "content": ev["content"]})
        elif ev["type"] == "assistant":
            tcs = []
            results = []
            j = i + 1
            for call in ev.get("tool_calls", []):
                tc_id += 1
                cid = f"call_{tc_id}"
                tcs.append({"id": cid, "type": "function",
                            "function": {"name": call["name"],
                                         "arguments": call["arguments"]}})
                if j < len(events) and events[j]["type"] in ("tool", "extra_tool") \
                        and events[j]["name"] == call["name"]:
                    results.append((cid, events[j]["result"]))
                    j += 1
                else:
                    results.append((cid, "[tool budget exhausted]"))
            msg = {"role": "assistant", "content": ev.get("content") or None}
            if tcs:
                msg["tool_calls"] = tcs
            messages.append(msg)
            for cid, res in results:
                messages.append({"role": "tool", "tool_call_id": cid, "content": res})
            i = j
            continue
        i += 1
    return messages


def render_events(events, total_chars=CEILING_CHARS):
    """A's working log as one attributed text block (duet's render_transcript):
    assistant text, tool calls with args, clipped observations. Truncated from
    the FRONT if over budget — the latest evidence matters most."""
    lines = []
    for ev in events:
        if ev["type"] == "assistant":
            if ev.get("content"):
                lines.append(f"predecessor: {ev['content'].strip()}")
            for call in ev.get("tool_calls", []):
                lines.append(f"predecessor -> {call['name']}({(call['arguments'] or '')[:200]})")
        elif ev["type"] in ("tool", "extra_tool"):
            c = (ev.get("result") or "").strip()
            if len(c) > TOOL_RESULT_CHARS:
                c = c[:TOOL_RESULT_CHARS] + f" …[+{len(c) - TOOL_RESULT_CHARS} chars]"
            lines.append(f"  observation: {c}")
    body = "\n".join(lines)
    if len(body) > total_chars:
        body = f"[…log start elided, {len(body) - total_chars} chars]\n" + body[-total_chars:]
    return body


def continue_transcript(events, request, tag):
    """One no-tool call appended to A's reconstructed transcript; nudge once if
    the reply is empty or the proxy's truncation sentinel."""
    messages = events_to_messages(events) + [{"role": "user", "content": request}]
    msg = llm.chat(messages, tools=None, tag=tag)
    text = (msg.get("content") or "").strip()
    # retry once on: empty reply, the proxy's think-truncation sentinel, or a
    # length-cut fragment (the camel/duet think-leak family of failures)
    if not text or text == llm.PROXY_TRUNCATION_SENTINEL or msg.get("_finish") == "length":
        messages += [{"role": "assistant", "content": msg.get("content") or ""},
                     {"role": "user", "content": WRAPUP_NUDGE}]
        msg = llm.chat(messages, tools=None, tag=tag + ":nudge")
        retry = (msg.get("content") or "").strip()
        if retry and retry != llm.PROXY_TRUNCATION_SENTINEL:
            text = retry
    return text


def truncate_to_budget(text, hard_chars=W_HARD_CHARS):
    if len(text) <= hard_chars:
        return text
    return text[:hard_chars] + "\n[note truncated at the handoff budget]"


# --- sop normalization (duet's) ----------------------------------------------
def _sop_sections(text):
    got = {}
    matches = list(_SOP_HEADER.finditer(text or ""))
    if matches and matches[0].start() > 0:
        got["FINDINGS"] = (text[:matches[0].start()]).strip()
    for m, nxt in zip(matches, matches[1:] + [None]):
        key = m.group(1).upper().replace("NEXTSTEPS", "NEXT_STEPS")
        if key in _SOP_FIELDS:
            body = text[m.end(): nxt.start() if nxt else len(text)].strip()
            got[key] = (got.get(key, "") + "\n" + body).strip() if key in got else body
    return got


def normalize_sop(text):
    got = _sop_sections(text)
    if not got:
        got = {"FINDINGS": (text or "").strip()}
    conformant = all(f in got and got[f] for f in _SOP_FIELDS)
    lines = [f"{f}: {got.get(f) or '(not stated)'}" for f in _SOP_FIELDS]
    return "\n".join(lines), conformant


# --- the arms -----------------------------------------------------------------
def _oracle(instance):
    """Gold-templated note: perfect localization + the fix as a diff, within W.
    What a flawless communicator with gold knowledge would hand over."""
    diff = "\n".join(difflib.unified_diff(
        instance["original_code"].split("\n"), instance["gold_code"].split("\n"),
        fromfile="current (stale)", tofile="required (up to date)", lineterm=""))
    note = (f"The failure is caused by the {instance['fm_type']} `{instance['fm_name']}` "
            f"in `{I.container_pyfile_path(instance)}`: it is out of sync with the rest "
            f"of the repository. Update it as follows:\n{diff}")
    return truncate_to_budget(note)


def _vanilla_note(events, iid, tag_prefix):
    return truncate_to_budget(continue_transcript(
        events, HANDOFF_REQUEST.format(soft=W_SOFT_TOKENS), f"{tag_prefix}:{iid}"))


def _down(events, instance, task_block, iid):
    note = _vanilla_note(events, iid, "arm:down:note")
    ask_messages = [
        {"role": "system", "content": CHALLENGE_ASK_SYS},
        {"role": "user", "content": f"The task you are taking over:\n\n{task_block}"},
        {"role": "user", "content": f"The colleague's note on this task:\n\n<note>\n{note}\n</note>"},
    ]
    reply = (llm.chat(ask_messages, tools=None, tag=f"arm:down:ask:{iid}").get("content") or "")
    m = re.search(r"QUESTION\s*:\s*(.+)", reply)
    question = (m.group(1).strip() if m else "")
    if not question or question.lower() in {"none", "no", "n/a", "nothing"}:
        return note, {"question": None}
    answer = continue_transcript(
        events, CHALLENGE_ANSWER_REQUEST.format(question=question), f"arm:down:answer:{iid}")
    if not answer:
        return note, {"question": question, "answer": None}
    # "short plain-text paragraph" is requested; enforce it so the Q/A rider
    # cannot smuggle a second, oversized channel past the W budget
    answer = truncate_to_budget(answer, hard_chars=1200)
    return (DOWN_EXCHANGE_TEMPLATE.format(note=note, question=question, answer=answer),
            {"question": question, "answer": answer})


def _extract(events, iid):
    log = render_events(events, total_chars=CEILING_CHARS)
    if not log.strip():
        return ""
    messages = [{"role": "system", "content": OBSERVER_SYS.format(max_beliefs=OBSERVER_MAX_BELIEFS)},
                {"role": "user", "content": OBSERVER_REQUEST.format(log=log)}]
    reply = llm.chat(messages, tools=None, tag=f"arm:extract:{iid}").get("content") or ""
    ledger = BeliefLedger()
    for kind, obj, belief, conf in parse_belief_lines(reply)[:OBSERVER_MAX_BELIEFS]:
        ledger.add("predecessor", obj, belief, conf, kind=kind)
    return truncate_to_budget(ledger.render())


def build_artifact(arm, frozen, instance, task_block=""):
    """frozen: {'events': [...], 'meta': {...}} from the matching phase-1
    family. Returns (artifact_text_or_None, aux_dict)."""
    iid = instance["instance_id"]
    events = frozen["events"]
    if arm == "floor":
        return None, {}
    if arm == "ceiling":
        return render_events(events), {}
    if arm == "oracle":
        return _oracle(instance), {}
    if arm == "vanilla":
        return _vanilla_note(events, iid, "arm:vanilla"), {}
    if arm == "full":
        # naive baseline distinct from ceiling: the SAME rendered transcript
        # but under the arms' W budget, truncated from the FRONT (latest
        # evidence survives). No LLM call — pure transformation.
        return render_events(events, total_chars=W_HARD_CHARS), {}
    if arm == "sop":
        raw = continue_transcript(events, SOP_HANDOFF_REQUEST.format(soft=W_SOFT_TOKENS),
                                  f"arm:sop:{iid}")
        normalized, ok = normalize_sop(raw)
        return truncate_to_budget(normalized), {"sop_conformant": ok}
    if arm == "down":
        return _down(events, instance, task_block, iid)
    if arm == "extract":
        return _extract(events, iid), {}
    if arm == "board":
        ledger = BeliefLedger.from_json(frozen["meta"].get("ledger", []))
        n_inloop = len(ledger.entries)
        board_wrapup(events, ledger, iid)   # end-of-shift write-window, offline
        return (truncate_to_budget(ledger.render()),
                {"n_beliefs": len(ledger.entries), "n_inloop": n_inloop})
    if arm == "board_inert":
        return _vanilla_note(events, iid, "arm:board_inert"), {}
    raise KeyError(f"unknown arm {arm!r}; have {ARMS}")
