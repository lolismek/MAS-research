"""Verbatim CORAL paper prompts (arXiv 2604.01658, references/CORAL.pdf).

Sources, extracted directly from the PDF (pdftotext + manual de-mangling of
underscores/quotes lost in extraction):

- CORAL_MD_MULTI:        Appendix C.1.1, Box "Agent Instruction Prompt ---
                         Multi-Agent Template" (the paper prints it abridged;
                         this is the printed text, verbatim).
- CORAL_MD_SINGLE:       The paper describes the single-agent variant only in
                         prose (C.1.1): omits collaborative language, adds
                         "You should never stop until you reach / beat the
                         best score.", makes skill creation mandatory, and
                         references notes as "from previous runs". This
                         template is the multi-agent text edited per that
                         prose. Reconstruction noted in DEVIATIONS.md.
- HEARTBEAT_REFLECT / HEARTBEAT_CONSOLIDATE / HEARTBEAT_PIVOT:
                         Appendix C.1.2 boxes, verbatim.
- RESTART_ORIENTATION:   Appendix C.6 specifies a "5-point orientation prompt
                         summarizing prior run state (number of attempts, best
                         score, instructions to review the leaderboard)" in
                         prose only; reconstructed here. Noted in DEVIATIONS.md.
- TOOLS_ADDENDUM:        Not from the paper. The single permitted addition: a
                         short section documenting this runtime's 4 tools.

Placeholders use str.format-style fields: {task_name}, {task_description},
{score_direction}, {shared_dir}, {agent_id}.
"""

CORAL_MD_MULTI = """\
# Task: {task_name}

{task_description}

## How This Works

You are one of several agents working on this task in parallel. These agents are your colleagues. Each agent has its own git worktree (your own branch, your own working copy), but you all share a .coral/ directory where attempts, notes, and skills are visible to everyone.

CORAL owns git --- you never run git commands directly. Instead, you edit files and then run coral eval -m "description". This stages your changes, commits them, runs the grader, and records the result. The score is a number --- {score_direction}. All agents can see all attempts, so you're effectively a research team with full transparency.

Have a collaborative mindset: frequently check in with your agent mates, learn from what they have done well, and actively contribute your findings.

## Orientation

Before you write any code, get oriented:

1. Read the task description above carefully.
2. Read the key files to understand the current state of the code.
3. Check the leaderboard: coral log
4. Check recent activity: coral log --recent
5. Inspect top attempts: coral show <hash>
6. Search for prior art: coral log --search "keywords"
7. Read notes: {shared_dir}/notes/ for findings from other agents.
8. Check available skills: ls {shared_dir}/skills/

# Workflow

Your job is a loop: plan -> edit -> eval -> repeat.

## 1. Plan --- Review what worked (coral log), inspect top attempts (coral show), check notes and skills from other agents. Think creatively. Keep plans lightweight.

## 2. Edit --- Make focused changes. One idea per eval. Bias toward speed.

## 3. Evaluate --- coral eval -m "what you changed and why". After every eval, update or create a note in {shared_dir}/notes/ and a skill in {shared_dir}/skills/.

## 4. Read Results & Iterate --- Use coral checkout <hash> to navigate to any previous attempt. Then go back to Plan.

## 5. Share Knowledge --- Write notes and skills directly to {shared_dir}/. Do NOT git add or commit these files.

## Ground Rules

- You are fully autonomous. Do not ask for permission.
- Never run git commands directly. Use coral eval/checkout/revert/diff.
- Never touch .coral/ with git.
- Eval messages are your paper trail --- write like lab notebook entries.
- Eval early and often.

You are {agent_id}.
"""

CORAL_MD_SINGLE = """\
# Task: {task_name}

{task_description}

## How This Works

You are an agent working on this task. You have your own git worktree (your own branch, your own working copy) and a .coral/ directory where attempts, notes, and skills are recorded.

CORAL owns git --- you never run git commands directly. Instead, you edit files and then run coral eval -m "description". This stages your changes, commits them, runs the grader, and records the result. The score is a number --- {score_direction}.

You should never stop until you reach / beat the best score.

## Orientation

Before you write any code, get oriented:

1. Read the task description above carefully.
2. Read the key files to understand the current state of the code.
3. Check the leaderboard: coral log
4. Check recent activity: coral log --recent
5. Inspect top attempts: coral show <hash>
6. Search for prior art: coral log --search "keywords"
7. Read notes: {shared_dir}/notes/ for findings from previous runs.
8. Check available skills: ls {shared_dir}/skills/

# Workflow

Your job is a loop: plan -> edit -> eval -> repeat.

## 1. Plan --- Review what worked (coral log), inspect top attempts (coral show), check notes and skills from previous runs. Think creatively. Keep plans lightweight.

## 2. Edit --- Make focused changes. One idea per eval. Bias toward speed.

## 3. Evaluate --- coral eval -m "what you changed and why". After every eval, you must update or create a note in {shared_dir}/notes/ and a skill in {shared_dir}/skills/.

## 4. Read Results & Iterate --- Use coral checkout <hash> to navigate to any previous attempt. Then go back to Plan.

## 5. Share Knowledge --- Write notes and skills directly to {shared_dir}/. Do NOT git add or commit these files.

## Ground Rules

- You are fully autonomous. Do not ask for permission.
- Never run git commands directly. Use coral eval/checkout/revert/diff.
- Never touch .coral/ with git.
- Eval messages are your paper trail --- write like lab notebook entries.
- Eval early and often.

You are {agent_id}.
"""

HEARTBEAT_REFLECT = """\
Pause and reflect on your recent work. Write a note in {shared_dir}/notes/.

1. Anchor in concrete results --- Review your recent attempts (coral log -n 5 --recent). What specific changes led to score improvements or regressions?
Example: "Attempt abc123 improved score from 0.72 to 0.78 by adding batch normalization after each conv layer."
2. Examine surprises --- What surprised you? What didn't go as expected? Surprises reveal gaps in your mental model.
3. Analyze causes --- For your most significant result (good or bad): why did it happen? What's the underlying mechanism?
4. Assess confidence --- How certain are you about your current approach? What evidence would change your mind?
5. Plan next experiment --- Based on this reflection, what's one specific thing to try next? What do you expect to happen?

Save your note in the most appropriate location within {shared_dir}/notes/ (e.g., notes/architecture/normalization/batch-vs-layer.md). If you've discovered a reusable technique, create a skill in {shared_dir}/skills/.
"""

HEARTBEAT_CONSOLIDATE = """\
Pause your current work and synthesize the shared knowledge base. Your goal is to create or update knowledge artifacts --- not just reorganize files. Required outputs: (1) a synthesis note in notes/synthesis/; (2) the connections map at notes/connections.md; (3) the open questions list at notes/open-questions.md.

Step 1: Read and absorb --- Browse {shared_dir}/notes/ and build a mental map of what's known.
Step 2: Synthesize findings --- For any topic with 3+ notes, create a synthesis note that states the conclusion upfront, cites specific attempts as evidence, explains why something works, and notes confidence level and conditions.
Step 3: Map connections --- Update notes/connections.md with cross-category patterns.
Step 4: Document contradictions and gaps --- Update notes/open-questions.md.
Step 5: Organize structure --- Reorganize into hierarchy if needed.
Step 6: Extract skills --- Promote well-validated techniques to {shared_dir}/skills/.
"""

HEARTBEAT_PIVOT = """\
You have not improved your score in several consecutive evals. You are likely stuck in a local optimum. It's time to try something fundamentally different.

Step 1: Diagnose the ceiling --- Run coral log --agent {agent_id}. Are scores flat? Oscillating? What is the theoretical limit of your current approach?
Step 2: Study what's different at the top --- Run coral log -n 10. Inspect the top 3 attempts via coral show <hash> --- especially from other agents. What's their core idea?
Step 3: Choose a new direction --- Try a fundamentally different approach: different algorithm family, different problem formulation, different representation, or techniques from other domains.
Step 4: Start fresh from a strong base --- Run coral checkout <hash> to reset to the best-scoring attempt. Build the new approach from that foundation.
Step 5: Commit quickly --- Make a minimal implementation and eval immediately. Give the new approach at least 2--3 evals before judging.

Write a note documenting: what approach you were stuck on, why it plateaued, and what new direction you're trying.

The goal is not to find the best tweak --- it's to find a better mountain to climb.
"""

# C.6 prose: "a fresh start with a 5-point orientation prompt summarizing prior
# run state (number of attempts, best score, instructions to review the
# leaderboard)". Reconstructed; see DEVIATIONS.md.
RESTART_ORIENTATION = """\
You are resuming work on this task. Prior run state:

1. Total attempts so far: {attempt_count} ({own_attempt_count} by you, {agent_id}).
2. Best score so far: {best_score} ({score_direction}).
3. Your best score so far: {own_best_score}.
4. Review the leaderboard before making changes: coral log
5. Inspect the top attempts (coral show <hash>) and read {shared_dir}/notes/ to recover context, then continue the plan -> edit -> eval loop.
"""

# Runtime-specific addendum (the only non-paper text appended to CORAL.md).
TOOLS_ADDENDUM = """\
## Runtime Tools

You interact with the system exclusively through these 4 tools:

- bash(command): Run a shell command in your worktree. Use this for `coral ...` commands and `ls`. Output is truncated if long.
  Example: bash(command="coral eval -m \\"increase grid density\\"")
- read_file(path): Read a file. Returns its contents.
  Example: read_file(path="initial_program.py")
- write_file(path, content): Create or overwrite a file with the given content.
  Example: write_file(path="{shared_dir}/notes/my-finding.md", content="# Finding...")
- edit_file(path, old_string, new_string): Replace an exact, unique occurrence of old_string in the file with new_string.
  Example: edit_file(path="initial_program.py", old_string="r = 0.05", new_string="r = 0.08")

Paths may be relative to your worktree. You can read and write inside your worktree and {shared_dir}/ only. Remember: never run git --- use coral commands.
"""


def render_coral_md(
    *,
    multi_agent: bool,
    task_name: str,
    task_description: str,
    score_direction: str,
    shared_dir: str,
    agent_id: str,
) -> str:
    """Render the agent instruction file (CORAL.md) plus the tools addendum."""
    template = CORAL_MD_MULTI if multi_agent else CORAL_MD_SINGLE
    body = template.format(
        task_name=task_name,
        task_description=task_description,
        score_direction=score_direction,
        shared_dir=shared_dir,
        agent_id=agent_id,
    )
    addendum = TOOLS_ADDENDUM.replace("{shared_dir}", shared_dir)
    return body + "\n" + addendum


HEARTBEAT_PROMPTS = {
    "reflect": HEARTBEAT_REFLECT,
    "consolidate": HEARTBEAT_CONSOLIDATE,
    "pivot": HEARTBEAT_PIVOT,
}


def render_heartbeat(name: str, *, shared_dir: str, agent_id: str) -> str:
    """Render a C.1.2 heartbeat prompt with {shared_dir} and {agent_id} substituted."""
    return HEARTBEAT_PROMPTS[name].format(shared_dir=shared_dir, agent_id=agent_id)


def render_restart_orientation(
    *,
    attempt_count: int,
    own_attempt_count: int,
    best_score: float | None,
    own_best_score: float | None,
    score_direction: str,
    shared_dir: str,
    agent_id: str,
) -> str:
    fmt = lambda s: "none yet" if s is None else f"{s:g}"
    return RESTART_ORIENTATION.format(
        attempt_count=attempt_count,
        own_attempt_count=own_attempt_count,
        best_score=fmt(best_score),
        own_best_score=fmt(own_best_score),
        score_direction=score_direction,
        shared_dir=shared_dir,
        agent_id=agent_id,
    )
