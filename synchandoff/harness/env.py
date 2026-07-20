"""Docker instance environment.

One InstanceEnv = one container from the instance's prebuilt xuehang image
(repo + venv ready). Lifecycle: start() -> setup_out_of_sync() -> [agent acts
via exec/read/write] -> run_tests() -> stop(). After setup we commit the
out-of-sync state in the repo's git, so any later change the agent makes is
recoverable as `git diff HEAD` — that diff is what LA (localization accuracy)
is computed from, judge-free.

Images are amd64-only; on Apple Silicon Docker runs them under emulation
(fine for smoke tests; pilot/full batches run on native x86).
"""
import json
import re
import subprocess
import uuid

from . import instances as I

TEST_TIMEOUT = 600  # seconds, SyncMind's cap
_SUMMARY_KEYS = ["passed", "xpassed", "failed", "xfailed", "deselected", "skipped", "warning", "error"]


class InstanceEnv:
    def __init__(self, instance, platform="linux/amd64"):
        self.instance = instance
        self.image = I.image_for(instance)
        self.platform = platform
        self.name = f"sh_{instance['instance_id'][:40]}_{uuid.uuid4().hex[:6]}".replace("__", "_")
        self.pyfile = I.container_pyfile_path(instance)
        self.test_rel = I.unittest_rel_path(instance)
        meta = I.repo_meta(instance)
        self.extra_test_args = (meta.get("additional_unittest_command") or "").strip()

    # ---------------------------------------------------------------- lifecycle
    def start(self):
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)
        subprocess.run(
            ["docker", "run", "-d", "--name", self.name, "--platform", self.platform,
             self.image, "sleep", "infinity"],
            check=True, capture_output=True)

    def stop(self):
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)

    # ---------------------------------------------------------------- primitives
    def exec(self, cmd, timeout=TEST_TIMEOUT, workdir=I.WORKDIR):
        """Run a shell command in the container; returns (exit_code, output)."""
        try:
            r = subprocess.run(
                ["docker", "exec", "-w", workdir, self.name, "bash", "-c", cmd],
                capture_output=True, text=True, timeout=timeout)
            out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
            return r.returncode, out
        except subprocess.TimeoutExpired:
            return 124, f"[timed out after {timeout}s]"

    def write_file(self, path, content):
        r = subprocess.run(
            ["docker", "exec", "-i", self.name, "bash", "-c",
             f"mkdir -p $(dirname {path!r}) && cat > {path!r}"],
            input=content, text=True, capture_output=True)
        return r.returncode == 0

    def read_file(self, path):
        code, out = self.exec(f"cat {path!r}", timeout=30)
        return out if code == 0 else None

    # ---------------------------------------------------------------- task state
    def setup_out_of_sync(self):
        """Write the stale pyfile and commit the state as the git baseline."""
        from .splice import align_agent_context
        # Some images ship the package as a non-editable site-packages COPY
        # (e.g. flask), so repo edits would never load; SyncMind reinstalled
        # editable before every test run. Once per container is enough. Best
        # effort: some venvs lack the build backend offline (fastapi/pdm) but
        # are already editable — the out-of-sync tests failing as recorded
        # (checked in the G1 env smoke, and again by run_tests during scoring)
        # is the real correctness gate.
        code, out = self.exec(
            f"{I.VENV}/bin/pip install -e . --no-deps --no-build-isolation -q",
            timeout=300)
        if code != 0:
            code, out = self.exec(f"{I.VENV}/bin/pip install -e . --no-deps -q",
                                  timeout=300)
        self.editable_ok = (code == 0)
        stale = align_agent_context(self.instance["original_code"],
                                    self.instance["new_complete_context"])
        assert self.write_file(self.pyfile, stale), "failed to write stale pyfile"
        code, out = self.exec(
            "git config user.email sh@local && git config user.name synchandoff "
            "&& git add -A && git commit -qm out-of-sync-baseline", timeout=60)
        assert code == 0, f"baseline commit failed: {out}"

    def restore_gold(self):
        """Gold state = the up-to-date file content (ceiling-of-ceilings check)."""
        assert self.write_file(self.pyfile, self.instance["new_complete_context"])

    # ---------------------------------------------------------------- scoring
    def run_tests(self):
        """Run the instance's unit test; returns (summary dict, raw output)."""
        cmd = (f"{I.VENV}/bin/python -m pytest -v {self.test_rel} {self.extra_test_args}")
        code, out = self.exec(cmd, timeout=TEST_TIMEOUT)
        return parse_pytest_output(out), out

    def agent_diff(self):
        """What the agent changed since the last baseline commit. `git add -N`
        makes newly created files visible to diff; the default-context patch is
        replayable with `git apply` (phase 2 restores A's end state from it)."""
        self.exec("git add -N .", timeout=30)
        _, files = self.exec("git diff HEAD --name-only", timeout=30)
        _, diff = self.exec("git diff HEAD", timeout=30)
        return {"files": [f for f in files.strip().split("\n") if f], "diff": diff}

    def apply_patch(self, patch_text):
        """Replay a frozen phase-1 patch onto the out-of-sync state and commit
        it as the new baseline (B's LA is measured against A's end state)."""
        if patch_text.strip():
            assert self.write_file("/tmp/phase1.patch", patch_text)
            code, out = self.exec("git apply /tmp/phase1.patch", timeout=60)
            if code != 0:
                raise RuntimeError(f"phase-1 patch failed to apply: {out[-500:]}")
        code, out = self.exec(
            "git add -A && git commit -qm phase1-end-state --allow-empty", timeout=60)
        assert code == 0, f"phase-1 state commit failed: {out}"


def parse_pytest_output(out):
    """Parse the trailing '=== N passed, M failed in Xs ===' line into counts
    (same key set as the dataset's gold_summary/original_summary)."""
    summary = {k: 0 for k in _SUMMARY_KEYS}
    summary["total"] = 0
    tail = out[-4000:]
    m = None
    for m_ in re.finditer(r"=+ ([^=]*(?:passed|failed|error|skipped|xfailed|xpassed|deselected|warning)[^=]*) =+", tail):
        m = m_
    if not m:
        return summary
    for count, label in re.findall(r"(\d+) (passed|xpassed|failed|xfailed|deselected|skipped|warnings?|errors?)", m.group(1)):
        key = {"warnings": "warning", "errors": "error"}.get(label, label)
        summary[key] = int(count)
    summary["total"] = sum(summary[k] for k in ["passed", "xpassed", "failed", "xfailed", "skipped", "error"])
    return summary


def tests_pass(summary, gold_summary):
    """Success = no failures/errors and at least the gold number of passes."""
    return (summary["failed"] == 0 and summary["error"] == 0
            and summary["passed"] >= gold_summary.get("passed", 1) > 0)


def summaries_match(a, b, keys=("passed", "failed", "error")):
    return all(a.get(k, 0) == b.get(k, 0) for k in keys)
