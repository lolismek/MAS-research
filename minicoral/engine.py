"""Engine protocol + HFEngine + APIEngine (latent seam #1).

GenRequest carries reserved latent fields (capture_states, inject_embeds,
inject_kv). v1 behavior: HFEngine accepts capture_states (plumbing only,
state_handle stays None) and raises NotImplementedError on injection;
APIEngine raises on any of the three — latent transport is HF-only by design.

HFEngine serializes all generation through a single asyncio worker task: one
model per process, strictly sequential in v1. torch/transformers are imported
lazily so the rest of the package works on machines without them.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .toolcall import ParseError, ToolCall, parse_api_tool_calls, parse_qwen3


@dataclass
class InjectionPayload:
    """Latent material to inject at generation time (probe arms; v1 unused)."""

    kind: str  # "embeds" | "kv"
    data: Any = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class StateHandle:
    """Reference to captured hidden states (probe arms; v1 unused)."""

    ref: Any = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenRequest:
    messages: list[dict]
    tools: list[dict]
    max_new_tokens: int = 2048
    temperature: float = 0.7
    seed: int | None = None
    enable_thinking: bool = False
    # latent seams --- reserved; honored only by HFEngine, no-op/raise otherwise:
    capture_states: bool = False
    inject_embeds: InjectionPayload | None = None
    inject_kv: InjectionPayload | None = None


@dataclass
class GenResult:
    text: str
    tool_calls: list[ToolCall]
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    state_handle: StateHandle | None = None  # v1: always None
    thinking: str = ""
    parse_errors: list[ParseError] = field(default_factory=list)


class Engine(Protocol):
    async def generate(self, req: GenRequest) -> GenResult: ...

    def count_tokens(self, messages: list[dict], tools: list[dict]) -> int: ...


class HFEngine:
    """Local HuggingFace model (Qwen3). The only latent-capable backend."""

    def __init__(
        self,
        model_name: str,
        device: str = "auto",
        dtype: str = "bfloat16",
        max_context: int = 32768,
        model: Any = None,
        tokenizer: Any = None,
    ):
        self.model_name = model_name
        self.device = device
        self.dtype = dtype
        self.max_context = max_context
        self._model = model
        self._tokenizer = tokenizer
        self._queue: asyncio.Queue[tuple[GenRequest, asyncio.Future]] | None = None
        self._worker: asyncio.Task | None = None
        # M7 observability: the last latent flags that reached the engine.
        self.last_latent_flags: dict[str, Any] = {}

    # -- loading ----------------------------------------------------------

    def _load(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch_dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16,
                       "float32": torch.float32}[self.dtype]
        device_map = self.device if self.device != "auto" else "auto"
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name, torch_dtype=torch_dtype, device_map=device_map
        )
        self._model.eval()

    # -- worker -----------------------------------------------------------

    async def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._queue = asyncio.Queue()
            self._worker = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self) -> None:
        assert self._queue is not None
        while True:
            req, fut = await self._queue.get()
            if fut.cancelled():
                continue
            try:
                result = await asyncio.to_thread(self._generate_blocking, req)
                fut.set_result(result)
            except Exception as e:  # surface in the caller, keep the worker alive
                fut.set_exception(e)

    async def generate(self, req: GenRequest) -> GenResult:
        if req.inject_embeds is not None or req.inject_kv is not None:
            raise NotImplementedError(
                "latent injection is reserved for the probe arms (not in v1)"
            )
        self.last_latent_flags = {"capture_states": req.capture_states}
        await self._ensure_worker()
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._queue.put((req, fut))
        return await fut

    # -- blocking core (monkeypatched in model-free tests) -----------------

    def _generate_blocking(self, req: GenRequest) -> GenResult:
        import torch

        self._load()
        prompt_text = self._tokenizer.apply_chat_template(
            req.messages,
            tools=req.tools or None,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=req.enable_thinking,
        )
        inputs = self._tokenizer(prompt_text, return_tensors="pt").to(self._model.device)
        prompt_tokens = inputs.input_ids.shape[1]
        if req.seed is not None:
            torch.manual_seed(req.seed)
        do_sample = req.temperature > 0
        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=req.max_new_tokens,
                do_sample=do_sample,
                temperature=req.temperature if do_sample else None,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        completion_ids = out[0][prompt_tokens:]
        completion_tokens = len(completion_ids)
        raw = self._tokenizer.decode(completion_ids, skip_special_tokens=True)
        finish_reason = "length" if completion_tokens >= req.max_new_tokens else "stop"
        return self._package(raw, prompt_tokens, completion_tokens, finish_reason)

    def _package(
        self, raw: str, prompt_tokens: int, completion_tokens: int, finish_reason: str
    ) -> GenResult:
        parsed = parse_qwen3(raw)
        return GenResult(
            text=parsed.text,
            tool_calls=parsed.tool_calls,
            finish_reason="tool_calls" if parsed.tool_calls else finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            state_handle=None,
            thinking=parsed.thinking,
            parse_errors=parsed.errors,
        )

    def count_tokens(self, messages: list[dict], tools: list[dict]) -> int:
        self._load()
        text = self._tokenizer.apply_chat_template(
            messages, tools=tools or None, tokenize=False, add_generation_prompt=True
        )
        return len(self._tokenizer(text).input_ids)


def load_dotenv_key(name: str, search_from: Path | None = None) -> str | None:
    """Resolve a key from the environment, else from the nearest .env upward."""
    if os.environ.get(name):
        return os.environ[name]
    d = (search_from or Path.cwd()).resolve()
    for parent in [d, *d.parents]:
        env_file = parent / ".env"
        if env_file.is_file():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith(f"{name}="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    return None


class APIEngine:
    """OpenAI-compatible chat-completions backend with native tool calls."""

    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        client: Any = None,  # injectable for tests
    ):
        self.model_name = model_name
        if client is not None:
            self._client = client
        else:
            import openai

            key = api_key or load_dotenv_key(api_key_env)
            if not key:
                raise RuntimeError(
                    f"no API key: set {api_key_env} in the environment or a .env file"
                )
            self._client = openai.AsyncOpenAI(base_url=base_url, api_key=key)

    async def generate(self, req: GenRequest) -> GenResult:
        if req.capture_states or req.inject_embeds is not None or req.inject_kv is not None:
            raise NotImplementedError(
                "latent capture/injection requires the HF backend (engine.backend: hf)"
            )
        kwargs: dict[str, Any] = dict(
            model=self.model_name,
            messages=req.messages,
            max_tokens=req.max_new_tokens,
            temperature=req.temperature,
        )
        if req.tools:
            kwargs["tools"] = req.tools
        if req.seed is not None:
            kwargs["seed"] = req.seed
        resp = await self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        tool_calls, errors = parse_api_tool_calls(choice.message.tool_calls)
        usage = getattr(resp, "usage", None)
        return GenResult(
            text=choice.message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            state_handle=None,
            parse_errors=errors,
        )

    def count_tokens(self, messages: list[dict], tools: list[dict]) -> int:
        # No tokenizer for API models; ~4 chars/token heuristic on the JSON view.
        blob = json.dumps(messages) + json.dumps(tools)
        return len(blob) // 4


def build_engine(engine_cfg, model_name: str) -> Engine:
    """Construct the backend selected by engine.backend (config.EngineConfig)."""
    if engine_cfg.backend == "hf":
        return HFEngine(
            model_name=model_name,
            device=engine_cfg.device,
            dtype=engine_cfg.dtype,
            max_context=engine_cfg.max_context,
        )
    return APIEngine(
        model_name=model_name,
        base_url=engine_cfg.base_url,
        api_key_env=engine_cfg.api_key_env,
    )
