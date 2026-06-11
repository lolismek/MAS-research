"""M1/M1b gate (model-free part): HFEngine serialization + latent-flag policy,
APIEngine normalization with a fake client."""

import asyncio
from types import SimpleNamespace

import pytest

from minicoral.engine import (
    APIEngine,
    GenRequest,
    GenResult,
    HFEngine,
    InjectionPayload,
    load_dotenv_key,
)


def make_req(**kw):
    return GenRequest(messages=[{"role": "user", "content": "hi"}], tools=[], **kw)


def patched_hf_engine(monkeypatch, delay=0.0, record=None):
    eng = HFEngine(model_name="fake", model=object(), tokenizer=object())

    def fake_blocking(req):
        import time

        if record is not None:
            record.append(("start", time.monotonic()))
        time.sleep(delay)
        if record is not None:
            record.append(("end", time.monotonic()))
        return eng._package(
            '<tool_call>{"name": "bash", "arguments": {"command": "ls"}}</tool_call>',
            prompt_tokens=10, completion_tokens=5, finish_reason="stop",
        )

    monkeypatch.setattr(eng, "_generate_blocking", fake_blocking)
    return eng


async def test_hf_generate_parses_tool_call(monkeypatch):
    eng = patched_hf_engine(monkeypatch)
    res = await eng.generate(make_req())
    assert isinstance(res, GenResult)
    assert res.tool_calls[0].name == "bash"
    assert res.finish_reason == "tool_calls"
    assert res.state_handle is None


async def test_hf_concurrent_generates_serialize(monkeypatch):
    record = []
    eng = patched_hf_engine(monkeypatch, delay=0.05, record=record)
    await asyncio.gather(*(eng.generate(make_req()) for _ in range(4)))
    # Strictly sequential: events must alternate start/end with no nesting.
    kinds = [k for k, _ in record]
    assert kinds == ["start", "end"] * 4


async def test_hf_capture_states_accepted(monkeypatch):
    eng = patched_hf_engine(monkeypatch)
    await eng.generate(make_req(capture_states=True))
    assert eng.last_latent_flags == {"capture_states": True}


async def test_hf_injection_raises(monkeypatch):
    eng = patched_hf_engine(monkeypatch)
    with pytest.raises(NotImplementedError):
        await eng.generate(make_req(inject_embeds=InjectionPayload(kind="embeds")))
    with pytest.raises(NotImplementedError):
        await eng.generate(make_req(inject_kv=InjectionPayload(kind="kv")))


class FakeCompletions:
    def __init__(self):
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        message = SimpleNamespace(
            content="done",
            tool_calls=[SimpleNamespace(
                id="call_9",
                function=SimpleNamespace(name="read_file", arguments='{"path": "a.py"}'),
            )],
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason="tool_calls")],
            usage=SimpleNamespace(prompt_tokens=42, completion_tokens=7),
        )


def fake_client():
    completions = FakeCompletions()
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


async def test_api_engine_normalizes_native_calls():
    client, completions = fake_client()
    eng = APIEngine(model_name="gpt-5.4-mini", client=client)
    res = await eng.generate(make_req(seed=7))
    assert res.text == "done"
    assert res.tool_calls[0].name == "read_file"
    assert res.tool_calls[0].id == "call_9"
    assert res.prompt_tokens == 42 and res.completion_tokens == 7
    assert completions.last_kwargs["seed"] == 7
    assert completions.last_kwargs["model"] == "gpt-5.4-mini"


async def test_api_engine_latent_flags_raise():
    client, _ = fake_client()
    eng = APIEngine(model_name="m", client=client)
    for kw in (
        {"capture_states": True},
        {"inject_embeds": InjectionPayload(kind="embeds")},
        {"inject_kv": InjectionPayload(kind="kv")},
    ):
        with pytest.raises(NotImplementedError):
            await eng.generate(make_req(**kw))


def test_api_count_tokens_positive():
    client, _ = fake_client()
    eng = APIEngine(model_name="m", client=client)
    assert eng.count_tokens([{"role": "user", "content": "hello world"}], []) > 0


def test_load_dotenv_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MY_TEST_KEY", raising=False)
    (tmp_path / ".env").write_text("OTHER=1\nMY_TEST_KEY=secret-123\n")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    assert load_dotenv_key("MY_TEST_KEY", search_from=sub) == "secret-123"
    monkeypatch.setenv("MY_TEST_KEY", "env-wins")
    assert load_dotenv_key("MY_TEST_KEY", search_from=sub) == "env-wins"
