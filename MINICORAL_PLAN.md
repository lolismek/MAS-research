# mini-CORAL: paper-faithful CORAL re-implementation (branch `mini-coral`)

## Context

Repo `~/MAS-memory-research`, branch `mini-coral` (off `open-ended-discovery`; contains only `.gitignore`, `PROBE_PLAN.md`, `references/`). Goal: re-implement the CORAL framework (arXiv 2604.01658, `references/CORAL.pdf`) as faithfully to the **paper** as possible, so that the latent-note-transport arms from `PROBE_PLAN.md` can be plugged in later. No latent implementation now — only the seams. The latent probe proceeds in parallel on the other branch; this harness is the substrate the winning arm plugs into.

**Why not use the official repo** (`github.com/Human-Agent-Society/CORAL`, Apache 2.0): (a) it has grown past the paper — multi-island migration, lint_wiki heartbeat, budget classes/tune mode, parallel grader daemon, crash circuit-breakers, LiteLLM gateway, web UI — all excluded per user instruction; (b) its agents are coding-agent CLI subprocesses (Claude Code/OpenCode) talking to API models, but future latent capture/injection needs **in-process access to an HF model** (hidden states at note-write, `inputs_embeds`/KV injection at note-read). So: re-implement the paper-era behavioral spec with our own agent runtime. The repo remains the reference for prompt wording and schema details.

**User decisions:** Engine supports **both** backends from the start — local HF (Qwen3-8B GPU / Qwen3-4B Mac-MPS dev; the only latent-capable one) and an OpenAI-compatible API backend (gpt-5.4-mini via the Perplexity proxy, key in gitignored `.env`) to validate the harness produces CORAL-like dynamics with a strong model before blaming model weakness. Task: circle packing (n=26, maximize sum of radii, SOTA ≈ 2.6359). No co-author trailers on commits.

## Paper-era spec being reproduced (requirements)

- **Shared memory** `.coral/public/` (symlinked into each agent worktree): `attempts/<commit_hash>.json`, `notes/` (free markdown, optional creator/created frontmatter), `skills/<name>/SKILL.md` + scripts, `heartbeat/<agent_id>.json` + `global.json`, `eval_count`. `.coral/private/eval/grader.py` hidden from agents.
- **Attempt record**: commit_hash, agent_id, title (from `-m`), score (float|null), status `improved|baseline|regressed|crashed|timeout` (vs the **agent's own** previous best, direction-aware), parent_hash, timestamp ISO8601, feedback (grader text), checkpoint_hash (git snapshot of `.coral/public` at eval time).
- **`coral eval -m "msg"`** (paper C.2 order): commit in worktree → grade the commit in isolation (subprocess, hard timeout default 300s) → status vs own best → write attempt JSON → checkpoint shared state → increment global `eval_count` → return formatted result (+ any triggered heartbeat prompts) to the agent.
- **Agent-facing CLI** (paper Table 6 subset): `coral eval/log/show/checkout/diff/revert/notes/skills/heartbeat(view)`.
- **Heartbeats** (paper Table 7, exactly 3): reflect (every 1 eval, interval, local), consolidate (every 10 evals, interval, **global** counter — next agent to eval gets it), pivot (plateau: 5 consecutive non-improving evals, with cooldown — no refire until 5 more stale). Delivery adapted: appended to the eval result at the eval boundary (paper uses SIGINT+resume; equivalent semantics — context injected without discarding session).
- **Prompts**: system prompt = paper Appendix C.1.1 multi-agent CORAL.md template (single-agent variant too); heartbeat prompts = C.1.2 verbatim. **Re-extract wording verbatim from the PDF during M0** — don't trust session summaries. Only permitted addendum: a short "Runtime tools" section describing our 4 tool names.
- **Run control**: wall-clock budget (~3h), global no-improvement stop, `max_turns` 200 per agent session, dead-agent restart with 5-point orientation prompt (paper C.6).
- All deviations recorded in a `DEVIATIONS.md`.

## Layout

```
minicoral/
├── __main__.py        # python -m minicoral {start,validate,status} -c task.yaml [-o override.yaml]
├── config.py          # YAML → dataclasses (task/grader/agents/engine/run/transport/sharing)
├── prompts.py         # verbatim paper prompts (C.1.1 multi+single, C.1.2 ×3) + tools addendum
├── engine.py          # Engine protocol + HFEngine + APIEngine  (latent seam #1)
├── toolcall.py        # normalize Qwen3 <tool_call> parsing AND API native tool calls → ToolCall
├── tools.py           # ToolExecutor: bash/read_file/write_file/edit_file, path confinement,
│                      #   `coral`/`git` bash interception, note read/write hooks (seam #2)
├── agent.py           # AgentRuntime loop + 32k context management (compaction = session reset)
├── hub.py             # Attempt dataclass + attempts/notes/skills/eval_count/checkpoint CRUD
├── coral_cli.py       # CoralCLI: the eval pipeline + log/show/checkout/diff/revert/notes/skills
├── grader.py          # GraderRunner: isolated subprocess grading + hard timeout
├── heartbeat.py       # HeartbeatMonitor state machine (interval/plateau/cooldown)
├── workspace.py       # run dir, seed clone, worktrees+branches, symlinks, CORAL.md, .gitignore guard
├── orchestrator.py    # build everything, N agent asyncio tasks, staggered start, termination, restart
├── transport.py       # NoteTransport protocol + TextOnlyTransport (seam #3)
└── trajlog.py         # per-agent trajectory JSONL + run.events.jsonl

tasks/circle_packing/{task.yaml, seed/initial_program.py, eval/grader.py}   # vendored (Apache 2.0, attribute: SkyDiscover or CORAL examples/)
configs/{dev-mps.yaml, gpu-a100.yaml, api-gpt54mini.yaml}
tests/                 # pytest, model-free except marked
scripts/{setup_gpu.sh, smoke_engine.py}
DEVIATIONS.md
```

Per-run output: `results/<task>/<ts>/` with `.coral/{public,private,sidecars}/`, `repo/` (seed clone), `agents/agent-N/` (worktree, branch `agent-N`, `CORAL.md`, symlink `.coral/public`), `logs/*.traj.jsonl`, `run.events.jsonl`, `config.resolved.yaml`. Latent sidecars live in `.coral/sidecars/` (mirror of notes/ paths, **not** symlinked → invisible to agents by construction).

## Key interfaces (the seams that matter)

```python
# engine.py
@dataclass
class GenRequest:
    messages: list[dict]; tools: list[dict]
    max_new_tokens: int = 2048; temperature: float = 0.7; seed: int | None = None
    enable_thinking: bool = False
    # latent seams — reserved; honored only by HFEngine, no-op/raise otherwise:
    capture_states: bool = False
    inject_embeds: InjectionPayload | None = None
    inject_kv: InjectionPayload | None = None

@dataclass
class GenResult:
    text: str; tool_calls: list[ToolCall]; finish_reason: str
    prompt_tokens: int; completion_tokens: int
    state_handle: StateHandle | None      # v1: always None

class Engine(Protocol):
    async def generate(self, req: GenRequest) -> GenResult: ...
    def count_tokens(self, messages, tools) -> int: ...

class HFEngine:   # one model/process; asyncio.Queue + single worker task (strictly sequential v1)
class APIEngine:  # OpenAI-compatible client (base_url + key from .env); native tool-calls;
                  # raises if capture_states/inject_* set
```

```python
# transport.py
class NoteTransport(Protocol):
    def wants_capture(self) -> bool: ...
    def on_note_write(self, note_path, gen: GenResult | None, agent_id) -> Path | None: ...
    def on_note_read(self, note_path, agent_id) -> InjectionPayload | None: ...
class TextOnlyTransport: ...   # v1 default; config: transport.kind: text_only (tiny registry)
```

- **tools.py**: 4 tools — `bash(command)` (cwd=worktree, output truncated head+tail ~2000 chars), `read_file`, `write_file`, `edit_file`. Path confinement by resolved path (allow worktree + `.coral/public/`; deny `private/`, `sidecars/`, escapes). Bash `^coral\s` → parsed (shlex) and dispatched to in-process `CoralCLI`; `^git\s` → rejected with the paper's ground-rule message. Note hooks: `write_file`/`edit_file` under `notes/` → `transport.on_note_write(path, last_gen, agent_id)`; `read_file` under `notes/` → `on_note_read` (payload attached to ToolResult); bash fallback = mtime-scan of `notes/` after each bash call → payload-less `on_note_write(path, None, agent_id)`.
- **agent.py loop**: generate → execute tool calls sequentially (eval results arrive with heartbeat prompts pre-appended by CoralCLI) → tool-less turn gets a nudge → context check → repeat until stop. **Context management** (HF 32k): high-water ~24k → compaction **= session reset at eval boundaries**: [system CORAL.md] + 5-point orientation block (paper C.6 restart prompt: #attempts, best score, review-leaderboard instruction) + last eval result + pending heartbeats. Mid-turn overflow backstop: mechanical truncation of oldest non-system turns, logged.
- **coral_cli.eval**: exact C.2 pipeline above; grading runs on `git archive <hash> | tar -x` into a temp dir (agent can't symlink at the grader); `--allow-empty` commits so every eval has a hash.
- **grader.py**: `python private/eval/grader.py --code-dir <tmp>` subprocess, `asyncio.wait_for` + SIGKILL; grader prints JSON `{score, feedback}`; bad exit/parse → `crashed`. Circle-packing grader: run agent's program in a sub-subprocess, validate boundary + pairwise overlap at 1e-6, score = sum(radii), feedback includes gap to 2.6359.
- **heartbeat.py**: pure state machine driven by `on_eval(agent_id, attempt, global_count) -> list[rendered prompts]`; per-agent state mirrored to `.coral/public/heartbeat/*.json` for observability.
- **trajlog.py**: append-only JSONL per agent — event types `session_start, assistant, tool_call, tool_result, eval, heartbeat, compaction, note_write, note_read, agent_restart, error` with token counts and gen params. Must be sufficient to reconstruct any context the model ever saw (later Read→Impr / knowledge-access analyses).

## Config (YAML, paper D.1-shaped)

`tasks/circle_packing/task.yaml`: task{name,description,files,tips}, grader{timeout:300, direction:maximize, args, private:[eval/]}, agents{count:4, model, max_turns:200, heartbeat: [reflect 1/interval/local, consolidate 10/interval/global, pivot 5/plateau/local]}, engine{backend: hf|api, device:auto, dtype:bfloat16, max_context:32768, compact_at_tokens:24576, max_new_tokens:2048, temperature:0.7, thinking:false, tool_output_max_chars:2000}, run{wall_clock_hours:3.0, max_stale_evals:40, results_dir, seed}, transport{kind: text_only}, sharing{attempts,notes,skills: true}.

Overrides: `dev-mps.yaml` (Qwen3-4B, 2 agents, 0.5h, fp16 fallback), `gpu-a100.yaml` (Qwen3-8B defaults; optional YaRN 64k block), `api-gpt54mini.yaml` (backend: api, model gpt-5.4-mini via Perplexity base_url from `.env`).

## Milestones (each gated by verification; M0–M7 entirely on Mac)

| # | What | Verification |
|---|---|---|
| M0 | Skeleton + config + vendored circle-packing seed/grader + `validate` cmd + **verbatim prompt extraction from PDF** into prompts.py | `validate` scores the seed; pytest: grader accepts valid packing, rejects boundary/overlap @1e-6, times out a sleeper |
| M1 | Engine protocol + **HFEngine** (MPS/Qwen3-4B) + toolcall.py | smoke script emits parseable tool call; pytest on canned outputs (well-formed/malformed/multi-call/thinking-strip); concurrent generates serialize |
| M1b | **APIEngine** (OpenAI-compatible, `.env` key) | same smoke vs gpt-5.4-mini; capture/inject flags raise |
| M2 | workspace.py + tools.py | pytest: worktrees, symlinks, confinement denials (private/, sidecars/, `..`, symlink escape), truncation, git/coral interception |
| M3 | hub + grader + coral_cli (full eval pipeline, **no model** — scripted fake agent) | all 5 statuses exercised; attempt JSON has all fields; checkout/revert/diff round-trip; eval_count + checkpoint advance; log/show render |
| M4 | agent.py single-agent end-to-end + compaction + trajlog (run on API backend first — cheap strong-model validation; then MPS/4B) | 30-min run: ≥2 evals, ≥1 note, trajectory replayable; forced compaction (`compact_at_tokens:4000`) recovers orientation |
| M5 | heartbeat.py wired in | pytest trigger math incl. pivot cooldown (no refire at 6–9 stale, refire at 10); prompts visible in trajectory at right counts |
| M6 | orchestrator: multi-agent, termination, restart | 2-agent run: interleaved attempts; consolidate lands on whoever crosses global 10; killed agent restarts with orientation; clean wall-clock stop |
| M7 | transport seam + sidecar invisibility | RecordingTransport pytest: hooks fire (file tools + bash mtime fallback); planted sidecar invisible to ls/read/bash; capture_states plumbing reaches HFEngine |
| M8 | GPU pilot: setup_gpu.sh, Qwen3-8B, 4 agents × 3h (~$10) | run completes; leaderboard improves over seed; throughput + faithfulness checklist audited from trajectories |

≈ 9–11 dev-days. First GPU dollar at M8.

## Faithfulness checklist (audit at M8)

Memory layout/symlinks → hub+workspace · attempt schema+checkpoint hash → hub/coral_cli · C.2 eval order → coral_cli.eval · status taxonomy vs own best → eval step 4 · grader isolation+300s → grader.py+confinement · Table 6 CLI subset → coral_cli via bash interception · C.1.1 CORAL.md verbatim (+tools addendum, the only new text) → prompts.py · Table 7 heartbeats+cooldown → heartbeat.py · heartbeat-with-eval-result delivery (adapted from SIGINT+resume) → eval step 7 · .gitignore workspace guard + no raw git → workspace+tools · dead-agent restart w/ orientation → orchestrator · max_turns 200 / 3h / stale-stop → config+orchestrator · task.yaml D.1 schema → config.py · `validate` → __main__ · **DEVIATIONS.md**: in-process runtime + own tool names; eval-boundary heartbeat delivery; compaction-as-session-reset; sidecar mirror dir; CLI subset; Qwen3/gpt-5.4-mini instead of Opus 4.6.

## Risks → mitigations

1. **Qwen3-8B tool-call reliability over long loops** (top risk): 4-tool surface, strict schema validation with error-as-tool-result retry, exact example per tool in addendum, nudges; flip `thinking: true` if M4 fails; constrained decoding = last resort. API backend isolates harness bugs from model weakness.
2. **32k context**: compaction-as-reset is paper-sanctioned (C.6 restarts); externalized memory is the designed recovery; YaRN-64k config switch if resets exceed ~1 per 2–3 evals; trajlog measures reset cost.
3. **Throughput (1 model, N agents, sequential)**: est. ~15 turns/agent/h at N=4 on A100 → 8–20 evals/agent in 3h ≈ paper's math-suite counts. If short: lower max_new_tokens, N=3; batched decode later.
4. **Reward hacking**: grader in private/ (confined), grading from `git archive` snapshot, program subprocess w/ own timeout.
5. **Arbitrary bash on rented box**: unprivileged user, per-command timeout, no secrets in env; noted in README.
6. **Qwen3 too weak on the task**: that's the baseline condition, not a failure — and the API run disambiguates harness vs model. Seed is deliberately naive (headroom exists; scipy available, known route >2.6).

## Verification (end-to-end)

`python -m minicoral validate -c tasks/circle_packing/task.yaml` → seed scores. Pytest suite green (model-free core). M4 single-agent API run eyeballed turn-by-turn from trajectory JSONL. M6 two-agent MPS run shows cross-agent note reading. M8 pilot audited against the faithfulness checklist; `status` prints leaderboard.

## Out of scope (do not build)

Latent arm implementations (probe branch owns them) · islands/migration · lint_wiki · budget classes/tune · gateway/web UI · parallel grader workers · circuit breakers · session resume across machines · `coral heartbeat set/remove` (view only; stretch).
