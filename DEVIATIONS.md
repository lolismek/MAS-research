# DEVIATIONS.md

Every place mini-CORAL knowingly departs from the CORAL paper
(arXiv 2604.01658). Anything not listed here follows the paper-era behavioral
spec (appendices C.1–C.7, D.1). Section/table references are to the paper.

## Runtime

1. **In-process agent runtime with a 4-tool surface.** The paper runs
   coding-agent CLI subprocesses (Claude Code / OpenCode) against API models.
   We run our own loop (`agent.py`) over an Engine abstraction so the latent
   probe arms can capture hidden states at note-write and inject
   embeds/KV at note-read — impossible through a CLI subprocess. The agent's
   tools are `bash`, `read_file`, `write_file`, `edit_file`. The only
   non-paper prompt text is the "Runtime Tools" addendum appended to CORAL.md
   (`prompts.TOOLS_ADDENDUM`).
2. **Models.** Qwen3-8B (GPU) / Qwen3-4B (MPS dev) / gpt-5.4-mini (API
   validation) instead of claude-opus-4-6.
3. **Instruction file is `CORAL.md`** (the paper's Claude Code runtime names
   it CLAUDE.md), and the shared memory is exposed as a single
   `.coral/public` symlink in each worktree instead of per-category
   `.claude/notes`, `.claude/skills`, ... links (C.4). Same reachability,
   one mount point. `CORAL.md` is gitignored in worktrees so attempts
   contain only task code.
4. **Kickoff/nudge glue.** The initial user message ("Begin working on the
   task now..."), the tool-less-turn nudge, and the parse-error feedback
   message are runtime glue with no paper equivalent (the paper's runtimes
   supply their own).

## Prompts

5. **Single-agent CORAL.md template is reconstructed.** C.1.1 prints only the
   multi-agent template (itself marked "abridged") and describes the
   single-agent variant in prose; `prompts.CORAL_MD_SINGLE` is the
   multi-agent text edited per that prose.
6. **Restart orientation is reconstructed.** C.6 specifies the "5-point
   orientation prompt" in prose only (number of attempts, best score,
   review-the-leaderboard); `prompts.RESTART_ORIENTATION` realizes it.
7. **Typography.** `---`, quotes, and `->` arrows are kept as plain ASCII as
   extracted from the PDF; underscores in placeholders/paths were restored
   where PDF extraction dropped them (e.g. `eval_count`).

## Heartbeats

8. **Eval-boundary delivery instead of SIGINT+resume** (C.5). Prompts are
   appended to the eval result returned to the agent — equivalent semantics
   (context injected without discarding the session) without process
   signalling, since the runtime is in-process.
9. **View-only `coral heartbeat`.** `set`/`remove`/`reset` (agent-modifiable
   heartbeats) are not implemented.

## Context management

10. **Compaction = session reset at eval boundaries.** The paper's runtimes
    have native context compaction; with 32k local models we reset the
    session to [CORAL.md + orientation + last eval result] once the
    high-water mark is crossed and an eval boundary arrives (C.6 restarts
    sanction this shape). A mechanical truncation of oldest turns is the
    mid-turn overflow backstop. Both are logged as `compaction` events.

## Memory & evaluation

11. **`.coral/sidecars/` is new** — the latent transport's hidden mirror of
    notes/. It is never symlinked into worktrees and is confinement-denied;
    text-only runs never touch it.
12. **`checkpoint_hash` is added to the attempt schema** (the paper's example
    record lacks it); checkpoints are git commits of the whole
    `.coral/public/` made by a repo living at `.coral/public/.git`. The
    attempt JSON is written, checkpointed, then updated in place with the
    resulting hash (C.2 steps 5–6 order preserved).
13. **First-eval status is `baseline`** — the paper does not specify the
    no-prior-best case; we treat the agent's first scored attempt as
    establishing its baseline.
14. **Grader contract is a standalone script** printing
    `{"score": float|null, "feedback": str}` JSON, instead of the
    `TaskGrader`/`ScoreBundle` class hierarchy (D.1). Same isolation
    properties: child process, hard timeout (300 s default), grading runs on
    a `git archive` snapshot with escaping symlinks dropped, grader code in
    `.coral/private/` denied to agents.
15. **Attempt timestamps are microsecond-precision** ISO8601 (ordering).
16. **`sessions.json` resume-across-machines is not implemented** (C.6);
    dead-agent restart with the orientation prompt is.

## CLI

17. **Table 6 subset.** Agent-facing commands only
    (`eval/log/show/checkout/diff/revert/notes/skills/heartbeat`-view),
    dispatched in-process via bash interception. Orchestration is
    `python -m minicoral {start,validate,status}`; `runs`, `resume`, `stop`,
    `ui` are not implemented. Because `coral` is interception rather than a
    real binary (the paper's runtimes have one on PATH), a `run_dir/bin/coral`
    stub is placed on the bash PATH: `which coral` succeeds, and invoking it
    inside `&&`/pipe chains (which interception cannot see) returns guidance
    to re-run it standalone. Without the stub, 3 of 4 agents in the first
    live run concluded the CLI didn't exist and never evaluated.
18. **`coral checkout` is `git reset --hard <hash>`** on the agent branch
    (the next eval's parent is the checked-out attempt). `coral revert` is
    `reset --hard HEAD~1`.

## Security posture (Risks #4/#5)

19. **`bash` is not sandboxed.** Path confinement covers the file tools;
    sidecar/private invisibility for bash holds by construction (nothing in
    the worktree references them), not adversarially. Run on a rented box as
    an unprivileged user; the tool layer strips `*KEY*/*TOKEN*/*SECRET*`
    variables from the bash environment and enforces a per-command timeout.

## Excluded by scope (post-paper features of the official repo)

Islands/migration, lint_wiki, budget classes/tune mode, parallel grader
workers, crash circuit-breakers, LiteLLM gateway, web UI.
