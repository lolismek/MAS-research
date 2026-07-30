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
import json
import os
from dataclasses import dataclass, field

from agent import run_agent, continue_agent, TokenMeter
import prompts

DEFAULT_TOTAL_BUDGET = int(os.environ.get("CHAINLOSS_TOTAL_BUDGET", "32000"))

# Tail reserves carved out of a slice for its mandatory terminal artifact. The commit
# reserve is smaller: a commit is a decision line, a note is a written record.
NOTE_RESERVE = int(os.environ.get("CHAINLOSS_NOTE_RESERVE", "2500"))
COMMIT_RESERVE = int(os.environ.get("CHAINLOSS_COMMIT_RESERVE", "2000"))

# Channel width (note arm): ~300 words asked in the prompt; hard clip here. Constant
# across N by design — only the NUMBER of crossings varies with N.
NOTE_MAX_CHARS = int(os.environ.get("CHAINLOSS_NOTE_MAX_CHARS", "2000"))

# Transcript-arm render caps (the "lossless up to" caps, stated in PLAN.md): each
# tool result is clipped per-render; each shift's whole rendered log is clipped so
# eight logs still fit a 64k context alongside the task.
TRANSCRIPT_TOOL_CLIP = int(os.environ.get("CHAINLOSS_TRANSCRIPT_TOOL_CLIP", "1500"))
TRANSCRIPT_LOG_CLIP = int(os.environ.get("CHAINLOSS_TRANSCRIPT_LOG_CLIP", "12000"))

ARMS = ("note", "transcript")


@dataclass
class RelayResult:
    final: str                                    # terminal shift's text (parse FINAL ANSWER from it)
    arm: str = "note"
    n: int = 1
    slice_budget: int = 0
    shifts: list = field(default_factory=list)    # one AgentResult per shift
    payloads: list = field(default_factory=list)  # what crossed each edge (len == shifts_used - 1)
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


def _abort(result_kw, shifts, payloads, per_shift):
    """The USD safety cap tripped mid-run: publish an honest UNKNOWN."""
    return RelayResult(final="FINAL ANSWER: UNKNOWN", shifts=shifts, payloads=payloads,
                       per_shift=per_shift, committed=True, budget_exceeded=True,
                       **result_kw)


def run_relay(task_prompt, tool_names, client, model, *, n, arm="note",
              total_budget=DEFAULT_TOTAL_BUDGET, usd_budget=None) -> RelayResult:
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; have {ARMS}")
    slice_budget = total_budget // n
    result_kw = dict(arm=arm, n=n, slice_budget=slice_budget)

    shifts, payloads, per_shift, logs = [], [], [], []
    prev_note = None
    for i in range(n):
        is_last = i == n - 1
        role = f"shift_{i + 1}"
        meter = TokenMeter()
        ctx = [_task_layer(task_prompt)]
        if arm == "note" and prev_note is not None:
            ctx.append(_note_layer(prev_note))
        elif arm == "transcript" and logs:
            ctx.append(_logs_layer(logs))

        # The slice's tail reserve: the note arm must fund its wrap-up call; the
        # transcript arm's non-terminal shifts have no wrap-up, so the whole slice
        # is work (the control's honestly-cheaper channel, reported not hidden).
        if is_last:
            reserve = COMMIT_RESERVE
        else:
            reserve = NOTE_RESERVE if arm == "note" else 0
        work_budget = max(0, slice_budget - reserve)

        res = run_agent(role, prompts.SOLVER_SYS, ctx, tool_names, client, model,
                        work_budget=work_budget, meter=meter, usd_budget=usd_budget)
        if usd_budget is not None and usd_budget.exceeded:
            shifts.append(res)
            per_shift.append(_ledger(role, meter, slice_budget, work_budget, res, 0))
            return _abort(result_kw, shifts, payloads, per_shift)

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
                               per_shift=per_shift, committed=committed,
                               budget_exceeded=bool(usd_budget and usd_budget.exceeded),
                               **result_kw)

        # Non-terminal shift: NO early finish — even a shift that already wrote a
        # FINAL ANSWER line hands off (its claim crosses inside the payload).
        if arm == "note":
            steps_before = res.n_steps
            note_res = continue_agent(res, prompts.HANDOFF_REQUEST, client, model,
                                      meter=meter, slice_budget=slice_budget,
                                      usd_budget=usd_budget)
            # A truncated OR empty note must not cross the edge — the marker does.
            usable = note_res.final and not note_res.truncated
            payload = (_clip(note_res.final, NOTE_MAX_CHARS, prompts.NOTE_CLIP_MARKER)
                       if usable else prompts.TRUNCATED_MARKER)
            shifts.append(note_res)      # note_res.transcript is the full shift incl. the note
            per_shift.append(_ledger(role, meter, slice_budget, work_budget, note_res,
                                     note_res.n_steps - steps_before))
            payloads.append(payload)
            prev_note = payload
        else:
            log = render_own_log(res.transcript)
            shifts.append(res)
            per_shift.append(_ledger(role, meter, slice_budget, work_budget, res, 0))
            payloads.append(log)
            logs.append(log)

        if usd_budget is not None and usd_budget.exceeded:
            return _abort(result_kw, shifts, payloads, per_shift)

    raise AssertionError("unreachable: the terminal shift always returns")
