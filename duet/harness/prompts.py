"""Every literal prompt string in the harness, as a named constant (hygiene rule 7).

Prompt review = reading this one file. The rules these strings enforce (see
duet/PLAN.md "Prompt hygiene"):

  1. Four fixed context layers, in order: system (role + output contract ONLY) ->
     task (verbatim, delimited) -> arm-injected shared-state block (P2) -> working
     transcript. Arms may only touch layer 3; NONE of the strings here mention an
     arm, a board, or a memory.
  2. Protocol machinery rides in the tool schema, not prose (P2 concern).
  3. Inject at the moment, not in advance. The system prompt is neutral "solve the
     task": it says NOTHING about shifts, successors, hand-offs, or that anyone else
     exists. The hand-off request (HANDOFF_REQUEST) arrives only when the shift's
     budget is spent, as its own user message. The successor sees the predecessor's
     note framed (SUCCESSOR_PREAMBLE) as "notes from a colleague" — never as
     instructions and never blended into the task text.
  6. Truncation guards: TRUNCATED_MARKER is what crosses an edge when a producer's
     output was cut off, so raw unterminated reasoning never propagates.

These are shared by EVERY arm (vanilla included); arm-specific additions live in
store.py / arms.py (P2) and inject only at the shared-state layer.
"""

# --- Layer 1: the agent's system prompt (role + output contract only) ---------
# Neutral and position-blind. Every agent in the relay gets exactly this — the
# asymmetry comes from POSITION (which shift), never from a different persona
# (PLAN: "roles are NOT a variable"). No mention of shifts/successors/teammates:
# an agent is told only what its next action needs (rule 3).
SOLVER_SYS = (
    "You are working on the task given below. Think it through and use the available "
    "tools when they help you make progress. When you are confident in the answer, end "
    "your reply with a line in exactly this form:\n"
    "FINAL ANSWER: <your answer>\n"
    "If you cannot determine the answer, use:\n"
    "FINAL ANSWER: UNKNOWN"
)

# --- Layer 2: the task, delimited (rule 1 — verbatim, never paraphrased) -------
# The benchmark question is dropped in verbatim between these fences so it is
# unmistakably the task and nothing leaks into or out of it.
TASK_TEMPLATE = "Here is the task:\n\n<task>\n{task}\n</task>"

# GAIA-style attachment note, appended INSIDE the task layer (it is part of the
# task): the file is staged locally and the agent reads it with read_file.
ATTACHMENT_NOTE = (
    "\n\nAn attached file is available at this exact path:\n{path}\n"
    "Call read_file with that path to read its contents."
)

# --- The hand-off seam (rule 3 — injected only at budget exhaustion) ----------
# A shift agent hits its budget mid-investigation. This arrives as its own user
# message; the agent still holds its full working context, so the note is its
# genuine reflection — the natural artifact a real hand-off produces (the "vanilla
# payload"). It is NOT told the mechanics of how many shifts remain — only that a
# fresh worker who cannot see its work will continue.
HANDOFF_REQUEST = (
    "You have reached the end of your available time on this task, so you must stop "
    "working now — there is no more time to investigate and no tools are available to you "
    "for this message. Another worker will continue from where you left off. They will NOT "
    "see any of your work above — only the note you write now. Write a concise hand-off "
    "note, as plain text, covering: what you have established (with the evidence for it), "
    "what is still open or uncertain, and what you would try next. Do not call any tools "
    "and do not give a FINAL ANSWER line — just write the note."
)

# If the wrap-up call comes back empty (the model tried to call a tool / emitted only a
# reasoning trace instead of the requested text), re-ask once, firmly. The proxy parses
# Qwen's <tool_call> text into tool_calls even when we send no tool schemas, so the block
# is to insist on plain prose (there is genuinely no tool to run at a wrap-up).
WRAPUP_NUDGE = (
    "You did not write any text. There are no tools available now and no time left to "
    "investigate further. Respond with plain text only, providing exactly what the "
    "previous message asked for."
)

# How the successor sees that note (rule 3 — framed as reference, rule 4 — its own
# delimited block with an unambiguous preamble, never blended into the task).
SUCCESSOR_PREAMBLE = (
    "Notes from a colleague who worked on this task before you and has since stopped. "
    "This is their record of where things stand — it is background for you, not your "
    "instructions and not something you wrote. Continue the task from here; you may "
    "re-check anything they claim.\n\n"
    "<handoff_note>\n{note}\n</handoff_note>"
)

# The last shift cannot hand off — it must commit. Injected only if the final shift
# spends its budget without having emitted a FINAL ANSWER (rule 3).
FINAL_COMMIT_REQUEST = (
    "You have reached the end of the available time and you are the last worker on this "
    "task — there is no one to hand off to and no tools are available for this message, so "
    "you must commit now. Based on everything established so far, decide the answer as plain "
    "text (do not call any tools). End with a line in exactly this form:\n"
    "FINAL ANSWER: <your answer>\n"
    "If the evidence does not support a confident answer, use:\n"
    "FINAL ANSWER: UNKNOWN"
)

# Constrained retry when an agent that was SUPPOSED to finalize produced no parseable
# FINAL ANSWER line (format slip, not truncation) — mirrors camel's finalizer retry.
NO_FINAL_RETRY = (
    "You did not end with a 'FINAL ANSWER:' line. Decide now from everything above and "
    "output EXACTLY one line and nothing else:\n"
    "FINAL ANSWER: <your answer, or UNKNOWN>"
)

# --- No-usable-output guard (rule 6) ------------------------------------------
# What crosses an edge when a producer left nothing usable: output cut off mid-generation
# (token cap / step backstop / context wall), OR an empty wrap-up (the model declined to
# write a note even after the nudge). Either way we must NOT cross raw unterminated
# reasoning or an empty payload; a short honest marker crosses instead, so the successor
# treats it as "no note" rather than inheriting garbage or a blank.
TRUNCATED_MARKER = "[the previous worker did not leave a usable hand-off note]"
