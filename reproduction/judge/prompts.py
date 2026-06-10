"""Prompts for the two-stage trace judge.

Stage A (open reading) is deliberately taxonomy-blind: the judge close-reads
the trace and reports ANYTHING potentially problematic — including patterns
that might be innocent — so we get diagnostic material the MAST labels can't
capture, and so stage A can't be anchored by the taxonomy's vocabulary.

Stage B produces the 14 MAST binary labels in strict JSON, with a mandatory
verbatim evidence quote per flagged mode (the original MAST judge required an
example only in a freeform summary, and its judges systematically under-
detected 2.4/2.5 — both the paper's o1 labels and our gpt-5.4 runs emitted
zero). Stage B receives stage A's findings as additional signal.
"""

MAST_MODES = ['1.1', '1.2', '1.3', '1.4', '1.5',
              '2.1', '2.2', '2.3', '2.4', '2.5', '2.6',
              '3.1', '3.2', '3.3']

STAGE_A = """\
You are an expert analyst of multi-agent LLM systems. Below is the full \
execution trace of a multi-agent system attempting a task. Close-read it and \
report everything that could be problematic, suboptimal, or merely unusual — \
INCLUDING things that might turn out to be innocent. Do not limit yourself to \
fatal errors: redundancy, lost or unused information, instructions that were \
not followed exactly, repeated work, agents talking past each other, \
inconsistencies between what an agent says and does, state that silently \
disappears between steps, and missed opportunities all count.

Pay particular attention to information flow BETWEEN agents: what each agent \
knew, what it passed on, what was dropped, distorted, ignored, or re-derived \
from scratch.

Respond with a JSON object, and nothing else:
{
  "narrative": "<1 paragraph: chronological story of the run: what was attempted, how it unfolded, where it went wrong (or didn't)>",
  "task_outcome": {"completed": <true|false>, "basis": "<1 sentence>"},
  "findings": [
    {
      "description": "<what happened, specific>",
      "agents": ["<agent name(s) involved>"],
      "evidence": "<short VERBATIM quote(s) from the trace>",
      "impact": "<consequence for the run, or 'none observed'>",
      "possibly_innocent": <true|false>,
      "kind": "<your own 2-4 word label, free-form>"
    }
  ]
}
List findings in trace order. Be exhaustive: 5-20 findings is typical for a \
failing run. Quotes must appear verbatim in the trace.

=== BEGIN TRACE ===
{TRACE}
=== END TRACE ===
"""

STAGE_B = """\
You are labeling a multi-agent LLM system trace with the MAST failure-mode \
taxonomy. Below you get (1) the taxonomy definitions, (2) canonical examples \
of each mode, (3) an independent analyst's findings about this trace, and \
(4) the full trace.

For EACH of the 14 modes decide whether it occurs in this trace. Rules:
- Mark a mode present ONLY if you can quote verbatim trace evidence for it.
- Absence of evidence = absent. Do not infer from vibes.
- The modes most often missed by automated judges are 2.4 (Information \
Withholding: an agent possesses information relevant to another agent's \
current step — including code, fixes, or state it produced earlier — that \
never reaches that agent or the shared artifact) and 2.5 (Ignored Other \
Agent's Input: an agent's substantive contribution — a correction, answer, \
or fix — is received but not acted upon, e.g. a reviewer repeating an \
identical comment because the fix was never applied, or an orchestrator \
discarding a sub-agent's correct answer). Check for these as rigorously as \
the rest: require evidence, but do not skip them because they are subtle.
- A mode can be present even if the task ultimately succeeded.

Respond with a JSON object, and nothing else:
{
  "task_success": <true|false>,
  "summary": "<one sentence, the MAST-style failure summary>",
  "modes": {
    "1.1": {"present": <true|false>, "evidence": "<verbatim quote, or null>", "note": "<<=1 sentence, or null>"},
    ... same shape for every mode: 1.1 1.2 1.3 1.4 1.5 2.1 2.2 2.3 2.4 2.5 2.6 3.1 3.2 3.3
  }
}

=== MAST DEFINITIONS ===
{DEFINITIONS}

=== MAST CANONICAL EXAMPLES ===
{EXAMPLES}

=== INDEPENDENT ANALYST FINDINGS (advisory; verify against the trace) ===
{FINDINGS}

=== BEGIN TRACE ===
{TRACE}
=== END TRACE ===
"""


def build_stage_a(trace):
    return STAGE_A.replace('{TRACE}', trace)


def build_stage_b(trace, definitions, examples, findings_json):
    return (STAGE_B.replace('{DEFINITIONS}', definitions)
            .replace('{EXAMPLES}', examples)
            .replace('{FINDINGS}', findings_json)
            .replace('{TRACE}', trace))
