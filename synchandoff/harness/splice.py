"""Faithful port of SyncMind's aligner (syncmind/builds/aligner.py).

align_agent_context(original_code, new_complete_context) produces the
out-of-sync pyfile: the up-to-date file content with the target function's
body replaced by the stale version. Semantics kept line-for-line identical to
SyncMind (including the final autopep8 pass) so our env states match the ones
that produced initial_error_log / original_summary in the dataset.
"""
import ast
import logging

import autopep8

logger = logging.getLogger("synchandoff.splice")


def correct_indentation(code: str) -> str:
    try:
        return autopep8.fix_code(code, options={"indent_size": 4})
    except Exception as e:
        logger.error(f"autopep8 failed ({e}); returning uncorrected code")
        return code


def extract_function_name(input_code: str) -> str:
    try:
        parsed_code = ast.parse(input_code)
    except SyntaxError:
        return None
    for node in ast.walk(parsed_code):
        if isinstance(node, ast.FunctionDef):
            return node.name
    return None


def align_agent_context(agent_code: str, context_code: str) -> str:
    """Replace the first `def <name>` block in context_code with agent_code."""
    func_name = extract_function_name(agent_code)
    if not func_name:
        return agent_code

    aligned_agent_code = ""
    align_in_progress_flag, if_aligned_flag = False, False
    num_leading_spaces = 0

    context_lines = context_code.split("\n")
    line_count = 0
    for context_code_line in context_lines:
        line_count += 1
        if (if_aligned_flag is False) and (f"def {func_name}" in context_code_line):
            num_leading_spaces = len(context_code_line) - len(context_code_line.lstrip())
            leading_spaces = num_leading_spaces * " "
            for agent_code_line in agent_code.split("\n"):
                aligned_agent_code += leading_spaces + agent_code_line + "\n"
            align_in_progress_flag, if_aligned_flag = True, True
            continue

        if align_in_progress_flag is True:
            if context_code_line.replace(" ", "") == "":
                if line_count == len(context_lines):
                    align_in_progress_flag = False
                    aligned_agent_code += "\n"
                    break
                next_context_line = context_lines[line_count]
                if next_context_line.replace(" ", "") == "":
                    continue
                next_line_leading_spaces_num = len(next_context_line) - len(next_context_line.lstrip())
                if next_line_leading_spaces_num <= num_leading_spaces:
                    align_in_progress_flag = False
                    aligned_agent_code += "\n"

        if align_in_progress_flag is False:
            aligned_agent_code += context_code_line + "\n"

    if if_aligned_flag is False:
        logger.warning(f"function `{func_name}` not found in context; returning context unchanged")
    return correct_indentation(aligned_agent_code)
