"""M7 gate: transport seam end-to-end --- hooks fire through the real agent
loop (file tools + bash mtime fallback), sidecar mirror is invisible to the
agent tool surface, capture_states plumbing reaches HFEngine."""

import pytest

from minicoral.agent import AgentRuntime
from minicoral.config import load_config
from minicoral.coral_cli import CoralCLI
from minicoral.engine import GenResult, HFEngine, InjectionPayload
from minicoral.grader import GraderRunner
from minicoral.hub import Hub
from minicoral.toolcall import ToolCall
from minicoral.tools import ToolExecutor
from minicoral.trajlog import TrajLogger
from minicoral.transport import TextOnlyTransport, build_transport, register_transport
from minicoral.workspace import build_workspace


class RecordingTransport:
    """Probe-arm stand-in: records hook firings and mirrors notes to sidecars."""

    def __init__(self, sidecars_dir, capture=True):
        self.sidecars_dir = sidecars_dir
        self.capture = capture
        self.writes, self.reads = [], []

    def wants_capture(self):
        return self.capture

    def on_note_write(self, note_path, gen, agent_id):
        self.writes.append((note_path.name, gen is not None, agent_id))
        sidecar = self.sidecars_dir / "notes" / f"{note_path.name}.sidecar"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(f"latent-for:{note_path.name}")
        return sidecar

    def on_note_read(self, note_path, agent_id):
        self.reads.append((note_path.name, agent_id))
        return InjectionPayload(kind="embeds", meta={"note": note_path.name})


@pytest.fixture
def rig(task_yaml, tmp_path):
    cfg = load_config(task_yaml)
    cfg.run.results_dir = str(tmp_path / "results")
    cfg.agents.count = 1
    ws = build_workspace(cfg, run_ts="m7")
    transport = RecordingTransport(ws.sidecars_dir)
    hub = Hub(ws.public_dir, direction=cfg.grader.direction)
    grader = GraderRunner(ws.grader_path, timeout=30, args=cfg.grader.args)
    cli = CoralCLI(agent_id="agent-1", worktree=ws.worktree("agent-1"), hub=hub, grader=grader)
    ex = ToolExecutor(worktree=ws.worktree("agent-1"), public_dir=ws.public_dir,
                      coral=cli, transport=transport, agent_id="agent-1")
    return ws, transport, ex


def call(name, **arguments):
    return ToolCall(name=name, arguments=arguments)


async def test_hooks_fire_through_file_tools_and_bash(rig):
    ws, transport, ex = rig
    ex.last_gen = GenResult(text="", tool_calls=[], finish_reason="stop",
                            prompt_tokens=1, completion_tokens=1)

    await ex.execute(call("write_file", path=".coral/public/notes/w.md", content="# w"))
    await ex.execute(call("edit_file", path=".coral/public/notes/w.md",
                          old_string="# w", new_string="# w2"))
    await ex.execute(call("bash", command="echo b >> .coral/public/notes/b.md"))
    res = await ex.execute(call("read_file", path=".coral/public/notes/w.md"))

    assert transport.writes == [
        ("w.md", True, "agent-1"),   # write_file carries the generation
        ("w.md", True, "agent-1"),   # edit_file too
        ("b.md", False, "agent-1"),  # bash mtime fallback is payload-less
    ]
    assert transport.reads == [("w.md", "agent-1")]
    # injection payload from the read hook is attached to the tool result
    assert res.injection is not None and res.injection.meta["note"] == "w.md"


async def test_sidecars_written_but_invisible_to_agent(rig):
    ws, transport, ex = rig
    await ex.execute(call("write_file", path=".coral/public/notes/n.md", content="x"))
    sidecar = ws.sidecars_dir / "notes" / "n.md.sidecar"
    assert sidecar.is_file()  # the mirror exists...

    # ...but the agent cannot see it:
    # 1. the worktree's .coral/ contains only the public symlink
    res = await ex.execute(call("bash", command="ls -A .coral/"))
    assert res.content.strip() == "public"
    # 2. the shared dir itself has no sidecars entry
    res = await ex.execute(call("bash", command="ls -A .coral/public/"))
    assert "sidecar" not in res.content
    res = await ex.execute(call("bash", command="ls -R .coral/public/notes/"))
    assert "sidecar" not in res.content
    # 3. read_file at the real location is confinement-denied
    res = await ex.execute(call("read_file",
                                path="../../.coral/sidecars/notes/n.md.sidecar"))
    assert res.is_error and "denied" in res.content
    # 4. the natural relative guess through the symlinked dir doesn't resolve
    res = await ex.execute(call("bash", command="cat .coral/sidecars/notes/n.md.sidecar"))
    assert res.is_error


async def test_capture_states_reaches_hf_engine(rig, monkeypatch):
    ws, transport, ex = rig
    engine = HFEngine(model_name="fake", model=object(), tokenizer=object())
    monkeypatch.setattr(
        engine, "_generate_blocking",
        lambda req: engine._package("ok", 10, 2, "stop"),
    )
    monkeypatch.setattr(engine, "count_tokens", lambda m, t: 100)

    hub = Hub(ws.public_dir)
    traj = TrajLogger(ws.logs_dir / "agent-1.traj.jsonl", agent_id="agent-1")
    rt = AgentRuntime("agent-1", engine, ex, hub, traj, "system",
                      max_turns=1, transport=transport)
    await rt.run()
    assert engine.last_latent_flags == {"capture_states": True}

    transport.capture = False
    rt2 = AgentRuntime("agent-1", engine, ex, hub, traj, "system",
                       max_turns=1, transport=transport)
    await rt2.run()
    assert engine.last_latent_flags == {"capture_states": False}


def test_registry(tmp_path):
    t = build_transport("text_only", tmp_path)
    assert isinstance(t, TextOnlyTransport)
    assert not t.wants_capture()
    assert t.on_note_write(tmp_path / "n.md", None, "agent-1") is None
    assert t.on_note_read(tmp_path / "n.md", "agent-1") is None

    register_transport("recording_test", lambda d: RecordingTransport(d))
    assert isinstance(build_transport("recording_test", tmp_path), RecordingTransport)

    with pytest.raises(ValueError, match="unknown transport.kind"):
        build_transport("warp_drive", tmp_path)
