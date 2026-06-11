"""GraderRunner: isolated subprocess grading with a hard timeout (paper C.2 step 3, C.7).

The grader is a standalone script invoked as
    python <grader.py> --code-dir <dir> --args '<json>'
in its own process group. It must print one JSON object {"score": float|null,
"feedback": str} to stdout. Timeout -> SIGKILL of the whole group. The eval
pipeline maps the result to a status: timeout if the time limit was hit,
crashed if the grader misbehaved or returned a null score.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GradeResult:
    score: float | None
    feedback: str
    timed_out: bool = False
    crashed: bool = False  # grader bad exit / unparseable output / null score


class GraderRunner:
    def __init__(self, grader_path: Path, timeout: float, args: dict[str, Any] | None = None):
        self.grader_path = Path(grader_path)
        self.timeout = timeout
        self.args = args or {}

    async def grade(self, code_dir: Path) -> GradeResult:
        cmd = [
            sys.executable,
            str(self.grader_path),
            "--code-dir",
            str(code_dir),
            "--args",
            json.dumps(self.args),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,  # so we can SIGKILL the whole group
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
        except asyncio.TimeoutError:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            await proc.wait()
            return GradeResult(
                score=None,
                feedback=f"grader exceeded the {self.timeout:.0f}s hard timeout",
                timed_out=True,
            )

        out = stdout.decode(errors="replace")
        err = stderr.decode(errors="replace")
        if proc.returncode != 0:
            tail = err.strip().splitlines()[-10:]
            return GradeResult(
                score=None,
                feedback=f"grader exited with code {proc.returncode}:\n" + "\n".join(tail),
                crashed=True,
            )
        try:
            payload = json.loads(out.strip().splitlines()[-1])
            score = payload["score"]
            feedback = str(payload.get("feedback", ""))
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return GradeResult(
                score=None,
                feedback=f"grader output was not valid JSON ({e}): {out[:500]!r}",
                crashed=True,
            )
        if score is None:
            return GradeResult(score=None, feedback=feedback, crashed=True)
        return GradeResult(score=float(score), feedback=feedback)
