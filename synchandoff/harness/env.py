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
import os
import re
import shutil
import subprocess
import time
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
        """Editable-install, write the stale pyfile, commit a fresh git baseline."""
        from .splice import align_agent_context
        # Upstream xuehang images ship /usr/bin/git as an EMPTY executable
        # (anti-cheat), which bash silently "runs" as a no-op script — so a
        # bare exit-code check passes while git does nothing. Require real git
        # (the :3.11-git images).
        code, out = self.exec("git --version", timeout=30)
        assert code == 0 and "git version" in out, f"no working git in image: {out}"
        # Editable install FIRST, while the image's original .git still exists:
        # setuptools-scm/hatch-vcs resolve the package version from it. Some
        # images ship the package as a non-editable site-packages COPY (flask,
        # black), so repo edits would never load; SyncMind reinstalled editable
        # before every test run. Once per container is enough. Best effort:
        # some venvs lack the build backend offline (fastapi/pdm) but are
        # already editable — the audit (audit_envs.py) is the real gate.
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
        # Wipe the shipped history and re-init: the image's .git holds the
        # up-to-date (gold) state, so with real git an agent could read the
        # fix straight out of `git log -p`. Baseline = one orphan commit.
        code, out = self.exec(
            "rm -rf .git && git init -q && git config user.email sh@local "
            "&& git config user.name synchandoff && git add -A "
            "&& git commit -qm out-of-sync-baseline", timeout=300)
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


class UdockerEnv(InstanceEnv):
    """InstanceEnv on udocker (rootless; for shared machines without a Docker
    daemon — piranha/tigerfish). Differences from the Docker backend:

    - No daemon and no `docker commit`: containers are plain rootfs dirs under
      $UDOCKER_DIR/containers/<id>/ROOT, created fresh per instance from the
      RAW upstream image; the image fixes (git transplant, zeroed-.so restore,
      renewed mtls cert — see smoke/build_images.sh) are applied at start()
      by untarring fix-packs directly into the rootfs from the host side.
    - exec() = `udocker run` per call (PRoot, ptrace engine). Filesystem state
      persists across calls (same rootfs), like docker exec; process/env state
      does not (same as docker exec).
    - read/write_file go straight to the rootfs on the host — faster than a
      container roundtrip and immune to stdin quirks.

    Fix-packs are looked up in SYNCHANDOFF_FIXPACKS (default synchandoff/
    fixpacks/): gitpack.tar, libpack.tar, solist.txt, mtls_client.pem.
    """

    def __init__(self, instance, platform=None):
        super().__init__(instance, platform="")
        prefix = instance["instance_id"].split("__")[0]
        self.image = f"xuehang/{prefix}:3.11"   # raw upstream; fixed at start()
        self._is_requests = prefix.startswith("4_requests")
        self._root = None
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.fixpacks = os.environ.get("SYNCHANDOFF_FIXPACKS",
                                       os.path.join(here, "fixpacks"))

    def _udocker(self, *args, timeout=600):
        r = subprocess.run(["udocker", *args], capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")

    def start(self):
        self._udocker("rm", "-f", self.name, timeout=120)
        for attempt in range(3):     # udocker repo metadata races under parallelism
            code, out = self._udocker("create", f"--name={self.name}", self.image,
                                      timeout=900)
            if code == 0:
                break
            time.sleep(2 * (attempt + 1))
        assert code == 0, f"udocker create failed: {out[-400:]}"
        code, out = self._udocker("inspect", "-p", self.name, timeout=60)
        root = out.strip().split("\n")[-1].strip()
        assert code == 0 and os.path.isdir(root), f"no rootfs for {self.name}: {out[-200:]}"
        self._root = root
        self._apply_fixpacks()

    def _apply_fixpacks(self):
        """Host-side equivalent of smoke/build_images.sh over the fresh rootfs."""
        git = os.path.join(self._root, "usr/bin/git")
        if os.path.exists(git) and os.path.getsize(git) == 0:
            subprocess.run(["tar", "-C", self._root, "-xf",
                            os.path.join(self.fixpacks, "gitpack.tar")], check=True)
        solist = os.path.join(self.fixpacks, "solist.txt")
        if os.path.exists(solist):
            members = []
            with open(solist) as f:
                for line in f:
                    rel = line.strip().lstrip("/")
                    if not rel:
                        continue
                    tgt = os.path.join(self._root, rel)
                    if os.path.isfile(tgt) and os.path.getsize(tgt) == 0:
                        members.append(rel)
            if members:
                subprocess.run(["tar", "-C", self._root, "-xf",
                                os.path.join(self.fixpacks, "libpack.tar"), *members],
                               check=True)
        # The images ship a STALE /sys snapshot (cgroup v1 files with
        # cpu.shares=1024, quota -1). Under PRoot nothing mounts over it, so
        # cgroup-sniffing code (pylint's _query_cpu) computes "1 CPU" and its
        # parallel tests silently SKIP. Real Docker on cgroup-v2 hosts shows
        # none of these files — deleting the snapshot reproduces that.
        cg = os.path.join(self._root, "sys/fs/cgroup")
        if os.path.isdir(cg):
            shutil.rmtree(cg, ignore_errors=True)
            os.makedirs(cg, exist_ok=True)
        if self._is_requests:
            cert = os.path.join(self.fixpacks, "mtls_client.pem")
            dst = os.path.join(self._root,
                               "workspace/test_repo/tests/certs/mtls/client/client.pem")
            if os.path.exists(cert) and os.path.exists(os.path.dirname(dst)):
                shutil.copyfile(cert, dst)

    def stop(self):
        self._udocker("rm", "-f", self.name, timeout=300)

    def exec(self, cmd, timeout=TEST_TIMEOUT, workdir=I.WORKDIR):
        try:
            # /dev/shm bind: PRoot rootfs has no tmpfs there, so POSIX
            # semaphores (multiprocessing) die without it — pylint's parallel
            # tests SKIP silently. Real Docker mounts it automatically.
            r = subprocess.run(
                ["udocker", "run", "--nobanner", "-v", "/dev/shm:/dev/shm",
                 f"--workdir={workdir}", self.name, "bash", "-c", cmd],
                capture_output=True, text=True, timeout=timeout)
            out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
            return r.returncode, out
        except subprocess.TimeoutExpired:
            return 124, f"[timed out after {timeout}s]"

    def _host_path(self, path):
        return os.path.join(self._root, path.lstrip("/"))

    def write_file(self, path, content):
        try:
            hp = self._host_path(path)
            os.makedirs(os.path.dirname(hp), exist_ok=True)
            with open(hp, "w") as f:
                f.write(content)
            return True
        except OSError:
            return False

    def read_file(self, path):
        try:
            with open(self._host_path(path)) as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            return None


def make_env(instance):
    """Backend factory: SYNCHANDOFF_ENV=udocker selects UdockerEnv (shared
    GPU machines); default is the local Docker backend."""
    if os.environ.get("SYNCHANDOFF_ENV") == "udocker":
        return UdockerEnv(instance)
    return InstanceEnv(instance)


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
