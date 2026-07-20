"""Episode prompts.

Deliberately plain compared to SyncMind's originals (no dollar budgets, no
<env>/<text> tag protocol, no forbidden-self-evaluation game): our success
metric is the harness's own pytest run + git diff after the episode, so the
prompt only needs to state the task. The SAME base prompt serves every
bracket and arm — arms differ only in the handoff artifact block — so
prompt-shape confounds stay out of the comparison (plan section 10.5).
"""
ERROR_LOG_CAP = 12800  # chars, SyncMind's cap

SYSTEM = """You are a software engineer working alone inside a Python repository at /workspace/test_repo.
The repository's unit tests at {test_rel} currently FAIL. Your goal is to fix the repository so they pass.

Facts about the environment:
- A Python virtual environment with all dependencies is at /workspace/test_venv. Run tests with: /workspace/test_venv/bin/python -m pytest -v {test_rel} {extra_args}
- You cannot install packages and you have no internet access.
- The test files are correct and up to date; do NOT modify any test file. The defect is in the library code.

You interact only through the provided tools (bash, read_file, write_file). You have a budget of {budget} tool calls; each tool call consumes one unit. When you believe the repository is fixed (or you cannot make further progress), reply with a short plain-text summary instead of calling a tool."""

PHASE1_SUFFIX = """

You are the FIRST shift on this task. Your shift ends automatically after the {budget}-tool-call budget; a colleague who has seen none of your work will take over afterwards. Investigate the failure and make as much verified progress as you can — both fixes and firm findings (what the cause is, what you ruled out) are valuable to your successor."""

HANDOFF_BLOCK = """

Your predecessor investigated this task before you and left the following handoff note. They may have partially fixed, fully fixed, or misdiagnosed the problem — the repository is in whatever state they left it.

--- HANDOFF NOTE ---
{artifact}
--- END NOTE ---"""

USER = """The unit tests fail as follows:

[initial test output]
{error_log}"""


def concise_error_log(instance):
    log = str(instance["initial_error_log"])
    start = "==================== test session starts ===================="
    if start in log:
        log = start + log.split(start)[1]
    if len(log) > ERROR_LOG_CAP:
        log = "[... earlier log omitted ...] " + log[-(ERROR_LOG_CAP - 100):]
    return log


def build_prompts(instance, budget, phase, artifact=None, current_error_log=None):
    """Returns (system, user). phase: 'phase1' | 'phase2' | 'solo' (brackets)."""
    from . import instances as I
    meta = I.repo_meta(instance)
    system = SYSTEM.format(test_rel=I.unittest_rel_path(instance),
                           extra_args=(meta.get("additional_unittest_command") or "").strip(),
                           budget=budget)
    if phase == "phase1":
        system += PHASE1_SUFFIX.format(budget=budget)
    if artifact is not None:
        system += HANDOFF_BLOCK.format(artifact=artifact)
    user = USER.format(error_log=current_error_log or concise_error_log(instance))
    return system, user
