"""Thin Perplexity LLM client (OpenAI SDK against the Agent API).

Perplexity serves frontier models (e.g. openai/gpt-5.4-mini) via the OpenAI SDK
with base_url=https://api.perplexity.ai/v1 using the Responses API
(`client.responses.create(model=..., input=...)`). We try Responses first and
fall back to chat.completions. Returns (text, usage_dict) where usage_dict has
input_tokens / output_tokens / cost_usd.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C

_client = None


def get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=C.api_key(), base_url=C.PPLX_BASE_URL + "/v1")
    return _client


def _usage(model, in_tok, out_tok):
    pin, pout = C.PRICES.get(model, (0.0, 0.0))
    return {
        "input_tokens": in_tok or 0,
        "output_tokens": out_tok or 0,
        "cost_usd": (in_tok or 0) / 1e6 * pin + (out_tok or 0) / 1e6 * pout,
    }


def call_llm(prompt: str, model: str, temperature: float = 0.0,
             max_output_tokens: int = 4000):
    client = get_client()
    # Preferred: Responses API (documented path for frontier ids on Perplexity)
    try:
        try:
            resp = client.responses.create(
                model=model, input=prompt,
                temperature=temperature, max_output_tokens=max_output_tokens)
        except TypeError:               # some models reject temperature/max kw
            resp = client.responses.create(model=model, input=prompt)
        u = getattr(resp, "usage", None)
        in_tok = getattr(u, "input_tokens", None) if u else None
        out_tok = getattr(u, "output_tokens", None) if u else None
        return resp.output_text, _usage(model, in_tok, out_tok)
    except Exception as e_resp:
        # Fallback: chat.completions
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature)
            u = getattr(resp, "usage", None)
            in_tok = getattr(u, "prompt_tokens", None) if u else None
            out_tok = getattr(u, "completion_tokens", None) if u else None
            return resp.choices[0].message.content, _usage(model, in_tok, out_tok)
        except Exception as e_chat:
            raise RuntimeError(
                f"Both Responses and chat.completions failed for {model}.\n"
                f"  responses: {e_resp}\n  chat: {e_chat}")
