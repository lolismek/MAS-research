"""The chainloss RELAY: N shifts, one fixed total token budget, two channel arms.

Forked from multi-benchmark-eval:duet/harness/relay.py; the chain mechanics are
reshaped around the experiment's three requirements:

  1. FIXED TOTAL BUDGET, SPLIT EVENLY. `total_budget` completion tokens for the
     whole run; each of the N shifts gets the slice `total_budget // N` and a
     shift-scoped TokenMeter as its ledger. A slice reserves tail room for its
     mandatory terminal artifact (NOTE_RESERVE / COMMIT_RESERVE) so the wrap-up is
     never squeezed out by the solve loop.
  2. NO EARLY FINISH. In duet any shift could emit FINAL ANSWER and end the relay;
     here a non-terminal shift's FINAL ANSWER is deliberately ignored — it still
     writes its hand-off and the next shift still runs. The manipulated variable is
     the NUMBER OF EDGE CROSSINGS, so the chain length must not silently collapse.
     (An early-confident shift's answer naturally crosses inside its note — as a
     claim the successor may re-check, which is the phenomenon under study.)
  3. THE CHANNEL IS THE ARM.
       arm='note'       (treatment) the capped free-prose hand-off note; the wrap-up
                        call bills the slice, the note is hard-clipped at
                        NOTE_MAX_CHARS (constant channel width across N).
       arm='transcript' (lossless control) the successor inherits the rendered work
                        logs of ALL prior shifts (each shift's own actions +
                        observations, rendered once, never nested); no wrap-up call
                        is made, so the whole slice goes to work. Lossless is up to
                        the per-result render clip and the model context — both
                        logged design caps, not hidden ones.

N=1 runs this exact code path with zero edges: the single shift is terminal from
the start, so single-agent-vs-MAS is never an implementation difference.
"""
import hashlib
import json
import os
import random
from dataclasses import dataclass, field

from agent import run_agent, continue_agent, TokenMeter
import prompts

# Calibrated TWICE on 2026-07-30. First pass set 16k (natural N=1 spend is
# ~0.5-2k), but the pilot showed 16k/8 = 2k slices sit BELOW Qwen3.6's minimum
# viable generation with thinking on (~1-2k to close a think block): every N=8
# run died to 'length' clips with final='' — a floor artifact, not channel loss.
# 32k makes the N=8 slice (4k) viable while the budget stays non-binding at low N,
# which sharpens attribution: differences across N come from the crossings, not
# from starvation.
DEFAULT_TOTAL_BUDGET = int(os.environ.get("CHAINLOSS_TOTAL_BUDGET", "32000"))

# Tail reserves carved out of a slice for its mandatory terminal artifact. The commit
# reserve is smaller: a commit is a decision line, a note is a written record.
NOTE_RESERVE = int(os.environ.get("CHAINLOSS_NOTE_RESERVE", "2500"))
COMMIT_RESERVE = int(os.environ.get("CHAINLOSS_COMMIT_RESERVE", "2000"))

# Channel width (note arm): ~300 words asked in the prompt; hard clip here. Constant
# across N by design — only the NUMBER of crossings varies with N.
NOTE_MAX_CHARS = int(os.environ.get("CHAINLOSS_NOTE_MAX_CHARS", "2000"))

# Salvage floor for a 'length'-finished note whose text survived (think closed, cut
# mid-prose): at least this many chars or the marker crosses instead. Shakedown
# showed all-or-nothing discarding real notes (note yield 0/1 on fanout_001 n=2).
NOTE_MIN_SALVAGE_CHARS = int(os.environ.get("CHAINLOSS_NOTE_MIN_SALVAGE", "200"))

# Transcript-arm render caps (the "lossless up to" caps, stated in PLAN.md): each
# tool result is clipped per-render; each shift's whole rendered log is clipped so
# eight logs still fit a 64k context alongside the task.
TRANSCRIPT_TOOL_CLIP = int(os.environ.get("CHAINLOSS_TRANSCRIPT_TOOL_CLIP", "1500"))
TRANSCRIPT_LOG_CLIP = int(os.environ.get("CHAINLOSS_TRANSCRIPT_LOG_CLIP", "12000"))

# --- E1-mini Q&A arms (note_randq / note_epiq) ---------------------------------
# Note-arm mechanics unchanged; right AFTER the note, the shift answers QA_K sampled
# questions IN ITS OWN WORK CONTEXT (that's the experiment: latent task state leaking
# into the answers), and the Q&A crosses the edge alongside the note. The Q&A call
# gets its own token allowance OUTSIDE the relay budget (metered separately; the
# relay work is budget-identical to the plain note arm). Deliberate, documented
# confound: these arms spend extra tokens and cross a wider channel (note + ≤1500
# chars of Q&A) than the `note` baseline.
QA_K = int(os.environ.get("CHAINLOSS_QA_K", "3"))
QA_BUDGET = int(os.environ.get("CHAINLOSS_QA_BUDGET", "600"))      # per handoff, extra-budget
QA_MAX_CHARS = int(os.environ.get("CHAINLOSS_QA_MAX_CHARS", "1500"))

ARMS = ("note", "transcript", "note_randq", "note_epiq")
NOTE_ARMS = ("note", "note_randq", "note_epiq")   # note-channel mechanics
QA_ARMS = ("note_randq", "note_epiq")


def sample_questions(arm, task_id, shift, k=None):
    """Deterministic k-question sample from the arm's pool, seeded by (task_id, shift).
    sha256, not hash(): stable across processes so reruns ask the same questions."""
    pool = prompts.RANDQ_POOL if arm == "note_randq" else prompts.EPIQ_POOL
    seed = int(hashlib.sha256(f"{task_id}:{shift}".encode()).hexdigest(), 16) % (2 ** 32)
    return random.Random(seed).sample(list(pool), k if k is not None else QA_K)


@dataclass
class RelayResult:
    final: str                                    # terminal shift's text (parse FINAL ANSWER from it)
    arm: str = "note"
    n: int = 1
    slice_budget: int = 0
    shifts: list = field(default_factory=list)    # one AgentResult per shift
    payloads: list = field(default_factory=list)  # what crossed each edge (len == shifts_used - 1)
    qa_payloads: list = field(default_factory=list)  # QA arms: the Q&A block per edge
    per_shift: list = field(default_factory=list) # token ledger per shift (dicts)
    committed: bool = True
    budget_exceeded: bool = False                 # the USD safety cap, not the token budget

    @property
    def agents(self):
        return self.shifts

    @property
    def shifts_used(self):
        return len(self.shifts)

    @property
    def n_calls(self):
        return sum(a.n_steps for a in self.shifts)

    @property
    def n_tool_calls(self):
        return sum(a.n_tool_calls for a in self.shifts)

    @property
    def finish(self):
        return self.shifts[-1].finish if self.shifts else "stop"

    @property
    def completion_tokens_used(self):
        return sum(s["completion"] for s in self.per_shift)


def _task_layer(task_prompt):
    """Layer 2: the benchmark question verbatim, delimited."""
    return {"role": "user", "content": prompts.TASK_TEMPLATE.format(task=task_prompt)}


def _note_layer(note):
    """The predecessor's hand-off note, framed as reference material."""
    return {"role": "user", "content": prompts.SUCCESSOR_PREAMBLE.format(note=note)}


def _qa_layer(qa, arm):
    """The predecessor's hand-off Q&A block (note_randq / note_epiq), after the note."""
    tpl = prompts.QA_PREAMBLE_RANDQ if arm == "note_randq" else prompts.QA_PREAMBLE_EPIQ
    return {"role": "user", "content": tpl.format(qa=qa)}


def _run_handoff_qa(note_res, arm, task_id, shift, client, model, usd_budget):
    """Ask the shift QA_K sampled questions IN ITS OWN WORK CONTEXT (appended to the
    same conversation, right after its note) and render the Q&A block that crosses
    the edge. Metered on its own TokenMeter — the relay budget is untouched (the
    documented extra-compute confound). Returns (qa_payload, qa_meter)."""
    qs = sample_questions(arm, task_id, shift)
    numbered = "\n".join(f"{j}. {q}" for j, q in enumerate(qs, 1))
    tpl = prompts.QA_REQUEST_RANDQ if arm == "note_randq" else prompts.QA_REQUEST_EPIQ
    qa_meter = TokenMeter()
    qa_res = continue_agent(note_res, tpl.format(questions=numbered), client, model,
                            meter=qa_meter, slice_budget=QA_BUDGET, usd_budget=usd_budget)
    if qa_res.final:
        # A 'length'-cut answer still crosses: the Q&A is soft signal, not a record
        # whose truncation could mislead — and the clip marker flags the cut anyway.
        payload = _clip(prompts.QA_RENDER.format(questions=numbered, answers=qa_res.final),
                        QA_MAX_CHARS, prompts.QA_CLIP_MARKER)
    else:
        payload = prompts.QA_DEAD_MARKER
    return payload, qa_meter


def _logs_layer(logs):
    """The transcript arm's inherited block: ALL prior shifts' rendered logs,
    oldest first, each under an attributed header."""
    body = "\n\n".join(
        prompts.TRANSCRIPT_HEADER.format(i=i + 1) + "\n" + log
        for i, log in enumerate(logs))
    return {"role": "user", "content": prompts.TRANSCRIPTS_PREAMBLE.format(logs=body)}


def _clip(s, cap, marker):
    s = s or ""
    return s if len(s) <= cap else s[:cap] + marker


def _fmt_args(arguments):
    """One-line render of a tool call's arguments (clipped)."""
    try:
        a = arguments if isinstance(arguments, dict) else json.loads(arguments or "{}")
        s = ", ".join(f"{k}={v!r}" for k, v in a.items())
    except Exception:
        s = str(arguments or "")
    return s if len(s) <= 200 else s[:200] + "…"


def render_own_log(transcript):
    """A shift's OWN work, rendered once for the transcript arm: its assistant text
    and tool I/O, in order. System/user layers (task, inherited block, wrap-up asks)
    are EXCLUDED — the successor already holds the task, and including an inherited
    render inside a render would nest the whole history exponentially. Recovered CoT
    (`reasoning_content`) is excluded too: the control's channel carries the work
    products (actions, observations, stated conclusions), not raw thought."""
    idx = {}
    for m in transcript:
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function") or {}
            idx[tc.get("id")] = fn.get("name", "tool")
    lines = []
    for m in transcript:
        role = m.get("role")
        if role == "assistant":
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                lines.append(f"-> called {fn.get('name', 'tool')}({_fmt_args(fn.get('arguments'))})")
            if (m.get("content") or "").strip():
                lines.append(m["content"].strip())
        elif role == "tool":
            name = idx.get(m.get("tool_call_id"), "tool")
            body = _clip((m.get("content") or "").strip(), TRANSCRIPT_TOOL_CLIP,
                         "\n…[result clipped in this log]")
            lines.append(f"[{name} returned]\n{body}")
    return _clip("\n\n".join(lines), TRANSCRIPT_LOG_CLIP, "\n…[log clipped at cap]")


def _ledger(role, meter, slice_budget, work_budget, res, wrapup_calls):
    return dict(role=role, finish=res.finish, model_calls=meter.calls,
                wrapup_calls=wrapup_calls, tool_calls=res.n_tool_calls,
                completion=meter.completion, prompt=meter.prompt,
                slice_budget=slice_budget, work_budget=work_budget,
                overrun=max(0, meter.completion - slice_budget))


def _abort(result_kw, shifts, payloads, per_shift, qa_payloads=()):
    """The USD safety cap tripped mid-run: publish an honest UNKNOWN."""
    return RelayResult(final="FINAL ANSWER: UNKNOWN", shifts=shifts, payloads=payloads,
                       qa_payloads=list(qa_payloads), per_shift=per_shift,
                       committed=True, budget_exceeded=True, **result_kw)


def run_relay(task_prompt, tool_names, client, model, *, n, arm="note",
              total_budget=DEFAULT_TOTAL_BUDGET, usd_budget=None,
              task_id=None) -> RelayResult:
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; have {ARMS}")
    slice_budget = total_budget // n
    result_kw = dict(arm=arm, n=n, slice_budget=slice_budget)
    # QA arms sample questions seeded by (task_id, shift); a stable fallback keeps
    # direct run_relay callers (tests) deterministic too.
    qa_task_id = task_id if task_id is not None else task_prompt[:64]

    shifts, payloads, qa_payloads, per_shift, logs = [], [], [], [], []
    prev_note = prev_qa = None
    for i in range(n):
        is_last = i == n - 1
        role = f"shift_{i + 1}"
        meter = TokenMeter()
        ctx = [_task_layer(task_prompt)]
        if arm in NOTE_ARMS and prev_note is not None:
            ctx.append(_note_layer(prev_note))
            if arm in QA_ARMS and prev_qa is not None:
                ctx.append(_qa_layer(prev_qa, arm))
        elif arm == "transcript" and logs:
            ctx.append(_logs_layer(logs))

        # The slice's tail reserve: the note arm must fund its wrap-up call; the
        # transcript arm's non-terminal shifts have no wrap-up, so the whole slice
        # is work (the control's honestly-cheaper channel, reported not hidden).
        if is_last:
            reserve = COMMIT_RESERVE
        else:
            reserve = NOTE_RESERVE if arm in NOTE_ARMS else 0
        # Scale down at small slices (high N / low budget): the reserve must never
        # eat the whole slice, or high-N shifts would do zero work by construction.
        reserve = min(reserve, slice_budget // 2)
        work_budget = max(0, slice_budget - reserve)

        res = run_agent(role, prompts.SOLVER_SYS, ctx, tool_names, client, model,
                        work_budget=work_budget, meter=meter, usd_budget=usd_budget)
        if usd_budget is not None and usd_budget.exceeded:
            shifts.append(res)
            per_shift.append(_ledger(role, meter, slice_budget, work_budget, res, 0))
            return _abort(result_kw, shifts, payloads, per_shift, qa_payloads)

        if is_last:
            # The terminal shift must commit. If its loop ended without a FINAL
            # ANSWER line (budget / clean stop without the line / truncation), force
            # the commit from its working memory; one constrained retry on a format
            # slip (duet's finalizer pattern).
            fin = res
            steps_before = res.n_steps
            if not res.has_final_answer:
                fin = continue_agent(res, prompts.FINAL_COMMIT_REQUEST, client, model,
                                     meter=meter, slice_budget=slice_budget,
                                     usd_budget=usd_budget)
                if not fin.has_final_answer and fin.finish != "ctx_overflow" and not (
                        usd_budget is not None and usd_budget.exceeded):
                    fin = continue_agent(fin, prompts.NO_FINAL_RETRY, client, model,
                                         meter=meter, slice_budget=slice_budget,
                                         usd_budget=usd_budget)
            shifts.append(fin)
            per_shift.append(_ledger(role, meter, slice_budget, work_budget, fin,
                                     fin.n_steps - steps_before))
            committed = fin.has_final_answer or fin.finish == "stop"
            return RelayResult(final=fin.final, shifts=shifts, payloads=payloads,
                               qa_payloads=qa_payloads, per_shift=per_shift,
                               committed=committed,
                               budget_exceeded=bool(usd_budget and usd_budget.exceeded),
                               **result_kw)

        # Non-terminal shift: NO early finish — even a shift that already wrote a
        # FINAL ANSWER line hands off (its claim crosses inside the payload).
        if arm in NOTE_ARMS:
            steps_before = res.n_steps
            note_res = continue_agent(res, prompts.HANDOFF_REQUEST, client, model,
                                      meter=meter, slice_budget=slice_budget,
                                      usd_budget=usd_budget)
            # An empty note must not cross the edge — the marker does. A truncated
            # ('length') note IS crossed when enough clean text survived (salvage,
            # see agent.continue_agent), explicitly clip-marked so the successor
            # knows the channel cut it, not its author.
            salvaged = note_res.truncated and len(note_res.final or "") >= NOTE_MIN_SALVAGE_CHARS
            usable = bool(note_res.final) and (not note_res.truncated or salvaged)
            if usable:
                payload = _clip(note_res.final, NOTE_MAX_CHARS, prompts.NOTE_CLIP_MARKER)
                if salvaged and not payload.endswith(prompts.NOTE_CLIP_MARKER):
                    payload += prompts.NOTE_CLIP_MARKER
            else:
                payload = prompts.TRUNCATED_MARKER
            led = _ledger(role, meter, slice_budget, work_budget, note_res,
                          note_res.n_steps - steps_before)
            if arm in QA_ARMS:
                # The hand-off Q&A, asked in the SAME conversation the shift worked
                # in (continue_agent appends to note_res.transcript, so the stored
                # shift transcript carries the Q&A turns too). Extra-budget: its own
                # meter, ledgered under qa_* — never charged to the relay budget.
                qa_payload, qa_meter = _run_handoff_qa(
                    note_res, arm, qa_task_id, i + 1, client, model, usd_budget)
                led.update(qa_calls=qa_meter.calls, qa_completion=qa_meter.completion,
                           qa_prompt=qa_meter.prompt)
                qa_payloads.append(qa_payload)
                prev_qa = qa_payload
            shifts.append(note_res)      # note_res.transcript is the full shift incl. the note
            per_shift.append(led)
            payloads.append(payload)
            prev_note = payload
        else:
            log = render_own_log(res.transcript)
            shifts.append(res)
            per_shift.append(_ledger(role, meter, slice_budget, work_budget, res, 0))
            payloads.append(log)
            logs.append(log)

        if usd_budget is not None and usd_budget.exceeded:
            return _abort(result_kw, shifts, payloads, per_shift, qa_payloads)

    raise AssertionError("unreachable: the terminal shift always returns")
