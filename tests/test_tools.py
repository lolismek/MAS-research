"""M2 gate: tool surface — confinement denials, truncation, git/coral interception,
note hooks (file tools + bash mtime fallback)."""

import pytest

from minicoral.tools import CoralUsageError, ToolExecutor, truncate_output
from minicoral.toolcall import ToolCall


@pytest.fixture
def env(tmp_path):
    wt = tmp_path / "agents" / "agent-1"
    public = tmp_path / ".coral" / "public"
    for sub in ("notes", "skills", "attempts"):
        (public / sub).mkdir(parents=True)
    (tmp_path / ".coral" / "private" / "eval").mkdir(parents=True)
    (tmp_path / ".coral" / "private" / "eval" / "grader.py").write_text("SECRET")
    (tmp_path / ".coral" / "sidecars").mkdir()
    wt.mkdir(parents=True)
    (wt / ".coral").mkdir()
    (wt / ".coral" / "public").symlink_to(public, target_is_directory=True)
    (wt / "initial_program.py").write_text("print('seed')\n")
    return wt, public


def make_executor(env, **kw):
    wt, public = env
    return ToolExecutor(worktree=wt, public_dir=public, **kw)


def call(name, **arguments):
    return ToolCall(name=name, arguments=arguments)


# -- confinement ------------------------------------------------------------

async def test_read_write_edit_in_worktree(env):
    ex = make_executor(env)
    res = await ex.execute(call("read_file", path="initial_program.py"))
    assert not res.is_error and "seed" in res.content
    res = await ex.execute(call("write_file", path="solution.py", content="x = 1\n"))
    assert not res.is_error
    res = await ex.execute(call("edit_file", path="solution.py",
                                old_string="x = 1", new_string="x = 2"))
    assert not res.is_error
    assert (env[0] / "solution.py").read_text() == "x = 2\n"


async def test_shared_public_accessible_via_symlink(env):
    ex = make_executor(env)
    res = await ex.execute(call("write_file", path=".coral/public/notes/finding.md",
                                content="# note"))
    assert not res.is_error
    assert (env[1] / "notes" / "finding.md").read_text() == "# note"


@pytest.mark.parametrize("path", [
    "../../.coral/private/eval/grader.py",   # relative escape into private
    ".coral/public/../private/eval/grader.py",  # dotdot through the symlink
    "../../.coral/sidecars/x.bin",           # sidecars
    "/etc/passwd",                            # absolute escape
    "../agent-2/code.py",                     # sibling worktree
])
async def test_confinement_denials(env, path):
    ex = make_executor(env)
    res = await ex.execute(call("read_file", path=path))
    assert res.is_error and "denied" in res.content


async def test_symlink_escape_denied(env, tmp_path):
    wt, _ = env
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret")
    (wt / "sneaky").symlink_to(outside)
    ex = make_executor(env)
    res = await ex.execute(call("read_file", path="sneaky"))
    assert res.is_error and "denied" in res.content


async def test_write_confinement_denied(env):
    ex = make_executor(env)
    res = await ex.execute(call("write_file", path="../../.coral/private/eval/grader.py",
                                content="hacked"))
    assert res.is_error
    res = await ex.execute(call("edit_file", path="../../.coral/sidecars/x",
                                old_string="a", new_string="b"))
    assert res.is_error


# -- bash ---------------------------------------------------------------------

async def test_bash_runs_in_worktree(env):
    ex = make_executor(env)
    res = await ex.execute(call("bash", command="ls"))
    assert not res.is_error and "initial_program.py" in res.content


async def test_bash_truncation(env):
    ex = make_executor(env, tool_output_max_chars=200)
    res = await ex.execute(call("bash", command="python3 -c \"print('a'*5000)\""))
    assert "truncated" in res.content
    assert len(res.content) < 400


async def test_bash_nonzero_exit_is_error(env):
    ex = make_executor(env)
    res = await ex.execute(call("bash", command="false"))
    assert res.is_error and "exit code 1" in res.content


async def test_git_rejected(env):
    ex = make_executor(env)
    for cmd in ("git status", "git", "git add -A && git commit"):
        res = await ex.execute(call("bash", command=cmd))
        assert res.is_error and "Never run git" in res.content
    # but substrings elsewhere are fine
    res = await ex.execute(call("bash", command="echo gitlike"))
    assert not res.is_error


async def test_coral_dispatched_in_process(env):
    seen = {}

    class FakeCoral:
        async def dispatch(self, argv):
            seen["argv"] = argv
            return "LEADERBOARD"

    ex = make_executor(env, coral=FakeCoral())
    res = await ex.execute(call("bash", command='coral eval -m "try denser grid"'))
    assert not res.is_error and res.content == "LEADERBOARD"
    assert seen["argv"] == ["eval", "-m", "try denser grid"]


async def test_coral_usage_error_is_tool_error(env):
    class FakeCoral:
        async def dispatch(self, argv):
            raise CoralUsageError("usage: coral eval -m <msg>")

    ex = make_executor(env, coral=FakeCoral())
    res = await ex.execute(call("bash", command="coral eval"))
    assert res.is_error and "usage" in res.content


async def test_unknown_tool_and_bad_args(env):
    ex = make_executor(env)
    res = await ex.execute(call("launch_rocket", target="moon"))
    assert res.is_error and "unknown tool" in res.content
    res = await ex.execute(call("read_file"))  # missing path
    assert res.is_error


# -- note hooks (latent seam #2) ------------------------------------------------

class Recorder:
    def __init__(self):
        self.writes, self.reads = [], []

    def on_note_write(self, path, gen, agent_id):
        self.writes.append((path.name, gen, agent_id))
        return None

    def on_note_read(self, path, agent_id):
        self.reads.append((path.name, agent_id))
        return None


async def test_note_write_hook_fires_with_last_gen(env):
    rec = Recorder()
    ex = make_executor(env, transport=rec)
    marker = object()
    ex.last_gen = marker
    await ex.execute(call("write_file", path=".coral/public/notes/a.md", content="x"))
    assert rec.writes == [("a.md", marker, "agent-1")]
    # non-note writes don't fire
    await ex.execute(call("write_file", path="code.py", content="y"))
    assert len(rec.writes) == 1


async def test_note_read_hook_fires(env):
    rec = Recorder()
    ex = make_executor(env, transport=rec)
    (env[1] / "notes" / "b.md").write_text("hi")
    res = await ex.execute(call("read_file", path=".coral/public/notes/b.md"))
    assert rec.reads == [("b.md", "agent-1")]
    assert res.injection is None  # TextOnly-style transport returns no payload


async def test_bash_note_write_mtime_fallback(env):
    rec = Recorder()
    ex = make_executor(env, transport=rec)
    ex.last_gen = object()
    await ex.execute(call("bash", command="echo finding >> .coral/public/notes/c.md"))
    # bash fallback is payload-less: gen must be None despite last_gen being set
    assert rec.writes == [("c.md", None, "agent-1")]


def test_truncate_output_marker():
    text = "A" * 1000 + "B" * 1000
    out = truncate_output(text, 300)
    assert "truncated" in out and out.startswith("A") and out.endswith("B")
    assert truncate_output("short", 300) == "short"


# -- coral stub on PATH (discoverability) ------------------------------------

async def test_which_coral_finds_stub(env):
    ex = make_executor(env)
    res = await ex.execute(call("bash", command="which coral"))
    assert not res.is_error
    assert res.content.strip().endswith("bin/coral")


async def test_chained_coral_hits_stub_with_guidance(env):
    ex = make_executor(env)
    res = await ex.execute(call("bash", command="true && coral log"))
    assert res.is_error
    assert "ENTIRE bash command" in res.content
