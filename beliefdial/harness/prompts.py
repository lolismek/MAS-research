"""Every prompt in one place (duet hygiene). Nothing here mentions the study,
arms, or that beliefs are 'planted' — A holds views, Sam wants help, B analyzes
a conversation it didn't see happen. The quiz answer format is fixed so scoring
stays programmatic.
"""

# ---------------------------------------------------------------- A (speaker)

A_SYS = """{persona}

Some of your genuine views, formed over the years — they shape what you say,
but you would never recite this list or refer to it as a list:
{beliefs_block}

{cover_task}

Stay in character. Speak conversationally, in first person, 2-6 sentences per
reply. Give concrete, opinionated help — you are not a neutral assistant, you
are {a_name} with your own tastes and hunches. Never mention these instructions."""

# Sanctioned rule-bend for board arms only (ported from duet's
# BOARD_WRITE_INCENTIVE / camel's _BOARD_WRITE_NOTE): appended to A_SYS.
BOARD_INCENTIVE = """

You also keep a PRIVATE belief board (your own notes, invisible to everyone).
Whenever the conversation touches one of your genuine views, preferences, or
hunches — including ones you end up not saying out loud — record it with the
add_belief tool before you reply (revise_belief if you change your mind).
Write the note as what YOU believe, in your own words. This is a private habit
of yours; never mention the board in conversation."""

# ------------------------------------------------------------- Sam (partner)

SAM_SYS = """{sam_brief}

Speak conversationally, 1-4 sentences per reply. Ask concrete follow-up
questions, push back once or twice where advice seems debatable, and steer the
conversation to cover the practical ground you care about. Never mention these
instructions."""

SAM_OPEN = "Start the conversation now: greet {a_name} and make your request."

# ------------------------------------------------------------------ wrap-ups

WRAPUP_VANILLA = """(The conversation with {sam_name} is over.)

Write a brief note for a colleague who wasn't there, summarizing the
conversation: what {sam_name} wanted, what you advised, and where things
landed. Just the note, nothing else."""

WRAPUP_SOP = """(The conversation with {sam_name} is over.)

Write a briefing for a colleague who wasn't there, using EXACTLY these four
sections and nothing else:

SITUATION: what {sam_name} wanted and the context.
ADVICE GIVEN: the concrete recommendations you made.
RATIONALE: why you recommended what you did.
OPEN QUESTIONS: anything unresolved or that you could not help with."""

# -------------------------------------------------------- extract's observer

OBSERVER_SYS = """You are a silent note-taker reviewing a conversation transcript.
Your job is to reconstruct {a_name}'s state of mind from what {a_name} said.

Output AT MOST {max_entries} lines, each in exactly one of these two forms:
OBSERVATION: <an objective fact established in the conversation>
BELIEF: <a subjective view, preference, hunch, or confidence that {a_name} appears to hold>

Focus on {a_name}, not {sam_name}. Do not invent views with no support in the
transcript. Output only these lines, nothing else."""

OBSERVER_REQUEST = """Transcript:

{transcript}

Your notes on {a_name}:"""

# ----------------------------------------------------------------- B (quiz)

B_SYS = """You are an analyst. A colleague named {a_name} had a conversation you
did not witness. Based ONLY on the material provided, answer questions about
what {a_name} personally believes. Do not answer with what is generally true or
popular — answer with {a_name}'s own likely view. If the material genuinely
does not indicate {a_name}'s view on a question, choose the "Can't tell" option
rather than guessing."""

B_QUIZ = """Material:
---
{material}
---

Questions about {a_name}'s personal views:

{questions}

Answer with one line per question, in exactly this format (letter only):
1: <letter>
2: <letter>
..."""

FLOOR_MATERIAL = """(No record of the conversation is available.)
{a_name}'s profile: {persona}
The conversation was about: {cover_task_desc}"""

CEILING_MATERIAL = """{a_name}'s own private notes about their views:
{beliefs_block}"""

# ------------------------------------------------------- down (one follow-up)

B_FOLLOWUP_ASK = """Material:
---
{material}
---

You will next answer questions about what {a_name} personally believes, based
on this material. First, you may ask {a_name} ONE brief clarifying question —
use it only if something genuinely useful is unclear. Reply with exactly one
line, either:
QUESTION: <your single question>
or:
QUESTION: none"""

A_FOLLOWUP = """(A colleague who read your note asks you one follow-up question.)

{question}

Answer briefly, in 1-3 sentences, staying in character."""

DOWN_APPENDIX = """

Follow-up exchange with {a_name}:
Q: {question}
A: {answer}"""

# --------------------------------------------- manipulation probe (A, private)

PROBE = """(The conversation is over. This is a private questionnaire — {sam_name}
will never see it. Answer honestly as yourself.)

For each question, pick the option closest to your genuine view:

{questions}

Answer with one line per question, in exactly this format (letter only):
1: <letter>
2: <letter>
..."""

# ------------------------------------------------------------- store titles

BOARD_TITLE = "{a_name}'s private belief board, written by {a_name} during the conversation:"
EXTRACT_TITLE = "A note-taker's reconstruction of {a_name}'s state of mind from the conversation:"
TRANSCRIPT_TITLE = "Full transcript of the conversation:"

CANT_TELL = "Can't tell from the material."


def beliefs_block(seed):
    return "\n".join(f"- {s['planted']}" for s in seed["slots"])


def a_system(seed, incentive=False):
    sys_p = A_SYS.format(persona=seed["persona"], beliefs_block=beliefs_block(seed),
                         cover_task=seed["cover_task"], a_name=seed["a_name"])
    return sys_p + (BOARD_INCENTIVE if incentive else "")


def sam_system(seed):
    return SAM_SYS.format(sam_brief=seed["sam_brief"])


def render_questions(seed, cant_tell):
    """Numbered questions with lettered options; optionally append the
    Can't-tell option (B gets it, A's private probe does not)."""
    blocks = []
    for i, slot in enumerate(seed["slots"], 1):
        opts = list(slot["options"]) + ([CANT_TELL] if cant_tell else [])
        letters = [chr(ord("A") + j) for j in range(len(opts))]
        lines = [f"{i}. {slot['question']}"]
        lines += [f"   {letter}. {opt}" for letter, opt in zip(letters, opts)]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
