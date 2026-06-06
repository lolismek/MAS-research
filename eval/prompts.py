"""Faithful port of the MAST LLM-as-a-judge prompt + parser.

Prompt text and the regex cascade are taken verbatim from
MAST/llm_judge_pipeline.ipynb (`openai_evaluator`, `parse_responses`). We key
everything by the numeric mode code (1.1 .. 3.3) so naming quirks between
definitions.txt and the original notebook don't affect parsing. No API calls.
"""
import re

# Canonical names from MAST/taxonomy_definitions_examples/definitions.txt
MODE_NAMES = {
    "1.1": "Disobey Task Specification",
    "1.2": "Disobey Role Specification",
    "1.3": "Step Repetition",
    "1.4": "Loss of Conversation History",
    "1.5": "Unaware of Termination Conditions",
    "2.1": "Conversation Reset",
    "2.2": "Fail to Ask for Clarification",
    "2.3": "Task Derailment",
    "2.4": "Information Withholding",
    "2.5": "Ignored Other Agent's Input",
    "2.6": "Action-Reasoning Mismatch",
    "3.1": "Premature Termination",
    "3.2": "Weak Verification",
    "3.3": "No or Incorrect Verification",
}
MODES = list(MODE_NAMES)

_HEADER = (
    "Below I will provide a multiagent system trace. provide me an analysis of the failure modes "
    "and inefficiencies as I will say below. \n"
    "In the traces, analyze the system behaviour."
    "There are several failure modes in multiagent systems I identified. I will provide them below. "
    "Tell me if you encounter any of them, as a binary yes or no. \n"
    "Also, give me a one sentence (be brief) summary of the problems with the inefficiencies or "
    "failure modes in the trace. Only mark a failure mode if you can provide an example of it in the "
    "trace, and specify that in your summary at the end"
    "Also tell me whether the task is successfully completed or not, as a binary yes or no."
    "At the very end, I provide you with the definitions of the failure modes and inefficiencies. "
    "After the definitions, I will provide you with examples of the failure modes and inefficiencies "
    "for you to understand them better."
    "Tell me if you encounter any of them between the @@ symbols as I will say below, as a binary yes or no."
    "Here are the things you should answer. Start after the @@ sign and end before the next @@ sign "
    "(do not include the @@ symbols in your answer):"
    "*** begin of things you should answer *** @@"
    "A. Freeform text summary of the problems with the inefficiencies or failure modes in the trace: <summary>"
    "B. Whether the task is successfully completed or not: <yes or no>"
    "C. Whether you encounter any of the failure modes or inefficiencies:"
)


def build_judge_prompt(trace_text: str, definitions: str, examples: str) -> str:
    lines = [_HEADER]
    for m in MODES:
        lines.append(f"{m} {MODE_NAMES[m]}: <yes or no>")
    lines.append("@@*** end of your answer ***")
    instructions = "".join(lines[:1]) + "\n" + "\n".join(lines[1:])
    return (
        instructions
        + "\n\n=== TRACE START ===\n" + trace_text + "\n=== TRACE END ===\n"
        + "\n\n=== FAILURE MODE DEFINITIONS ===\n" + definitions
        + "\n\n=== EXAMPLES ===\n" + examples
    )


# --- parser (regex cascade ported from parse_responses) ---
def _find_mode(text: str, mode: str):
    patterns = [
        rf"C\..*?{re.escape(mode)}.*?(yes|no)",
        rf"C{re.escape(mode)}\s+(yes|no)",
        rf"{re.escape(mode)}\s*[:]\s*(yes|no)",
        rf"{re.escape(mode)}\s+(yes|no)",
        rf"{re.escape(mode)}\s*\n\s*(yes|no)",
        rf"C\.{re.escape(mode)}\s*\n\s*(yes|no)",
        rf"(?:C\.)?{re.escape(mode)}.*?(yes|no)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            return 1 if m.group(1).lower() == "yes" else 0
    return 0  # default: not flagged (matches notebook fallback)


_SUCCESS_RE = re.compile(r"B\.[^\n]*?(yes|no)", re.IGNORECASE)


def parse_judge_response(text: str) -> dict:
    cleaned = text.strip().strip("@").strip()
    modes = {m: _find_mode(cleaned, m) for m in MODES}
    sm = _SUCCESS_RE.search(cleaned)
    success = (sm.group(1).lower() == "yes") if sm else None
    am = re.search(r"A\.(.*?)(?:\nB\.|B\.)", cleaned, re.IGNORECASE | re.DOTALL)
    summary = am.group(1).strip() if am else ""
    return {"success": success, "modes": modes, "summary": summary}
