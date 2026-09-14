"""Thin LLM clients with per-call cost logging.

TinkerChat  -> Qwen3.6 on Tinker (OpenAI-compatible /chat/completions). Reasoning comes
               back in `reasoning_content`; tool calls come back as XML text in `content`
               (<tool_call><function=NAME><parameter=K>V</parameter>...</function></tool_call>)
               which we parse ourselves. Tool results are fed back as a user turn wrapped
               in <tool_response> (Qwen's own template convention).
PplxResponses -> Perplexity /v1/responses (openai/gpt-5.5, gpt-5.4, gpt-5.4-mini). Exact
               cost is returned in usage.cost.

Every call appends one JSON line to LOG_PATH (default lip/traces/calls.jsonl):
  {ts, tag, backend, model, prompt_tokens, completion_tokens, cost_usd, latency_s}
"""
import json, os, re, threading, time
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(ROOT, ".env"))
LOG_PATH = os.environ.get("LIP_CALL_LOG", os.path.join(ROOT, "lip", "traces", "calls.jsonl"))
_log_lock = threading.Lock()

TINKER_BASE = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1"
TINKER_MODEL = "Qwen/Qwen3.6-35B-A3B"
TINKER_RATES = {"Qwen/Qwen3.6-35B-A3B": (0.36, 0.89)}   # $/M prompt, $/M completion (console, 2026-06-27)

def _log(rec):
    rec = dict(ts=time.time(), **rec)
    with _log_lock:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as f: f.write(json.dumps(rec) + "\n")

def spend(tag_prefix=None):
    """Total USD in the log (optionally only tags starting with tag_prefix)."""
    tot = 0.0
    if not os.path.exists(LOG_PATH): return 0.0
    for line in open(LOG_PATH):
        r = json.loads(line)
        if tag_prefix is None or str(r.get("tag", "")).startswith(tag_prefix): tot += r.get("cost_usd", 0.0)
    return tot

# ---------------------------------------------------------------- Qwen XML tool calls
_TC = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.S)
_FN = re.compile(r"<function=([\w.-]+)>(.*?)</function>", re.S)
_PA = re.compile(r"<parameter=([\w.-]+)>\s*(.*?)\s*</parameter>", re.S)

def parse_tool_calls(content):
    """Return (clean_text, [ {name, args} ]) from Qwen3.6 XML-style tool-call text."""
    calls = []
    for block in _TC.findall(content or ""):
        m = _FN.search(block)
        if not m: continue
        args = {k: v for k, v in _PA.findall(m.group(2))}
        calls.append(dict(name=m.group(1), args=args))
    clean = _TC.sub("", content or "").strip()
    return clean, calls

def tools_to_prompt(tools):
    """Render tool specs for the system prompt in the Qwen-native XML calling convention."""
    lines = ["# Tools", "You may call tools. To call one, emit exactly this XML (one call per turn):",
             "<tool_call>", "<function=NAME>", "<parameter=ARG>value</parameter>", "</function>", "</tool_call>",
             "", "Available functions:"]
    for t in tools:
        f = t["function"] if "function" in t else t
        props = f.get("parameters", {}).get("properties", {})
        sig = ", ".join(f"{k}: {v.get('type','string')}" + (f" — {v['description']}" if v.get("description") else "")
                        for k, v in props.items())
        lines.append(f"- {f['name']}({sig}): {f.get('description','')}")
    return "\n".join(lines)

class TinkerChat:
    def __init__(self, model=TINKER_MODEL, max_tokens=12000, timeout=300, retries=4):
        from openai import OpenAI
        self.c = OpenAI(api_key=os.environ["TINKER_API_KEY"], base_url=TINKER_BASE, timeout=timeout, max_retries=0)
        self.model, self.max_tokens, self.retries = model, max_tokens, retries

    def chat(self, messages, tag="", temperature=None, max_tokens=None):
        """messages: plain OpenAI-style dicts (system/user/assistant text only).
        Returns dict(reasoning, content, tool_calls, finish, usage, cost, latency)."""
        kw = dict(model=self.model, messages=messages, max_tokens=max_tokens or self.max_tokens)
        if temperature is not None: kw["temperature"] = temperature
        last = None
        for k in range(self.retries):
            t0 = time.time()
            try:
                r = self.c.chat.completions.create(**kw); break
            except Exception as e:
                last = e; time.sleep(2 * (k + 1))
        else:
            raise RuntimeError(f"tinker failed after {self.retries} tries: {last}")
        lat = time.time() - t0
        m = r.choices[0].message
        content = m.content or ""
        reasoning = getattr(m, "reasoning_content", None) or (m.model_extra or {}).get("reasoning_content") or ""
        if "</think>" in content:                      # older inline format, just in case
            reasoning = reasoning or content.split("</think>")[0].replace("<think>", "").strip()
            content = content.split("</think>")[-1].strip()
        clean, calls = parse_tool_calls(content)
        u = r.usage
        pt, ct = (u.prompt_tokens, u.completion_tokens) if u else (0, 0)
        pr, cr = TINKER_RATES.get(self.model, (0.36, 0.89))
        cost = (pt * pr + ct * cr) / 1e6
        _log(dict(tag=tag, backend="tinker", model=self.model, prompt_tokens=pt, completion_tokens=ct,
                  cost_usd=cost, latency_s=round(lat, 2), finish=r.choices[0].finish_reason))
        return dict(reasoning=reasoning, content=clean, raw_content=content, tool_calls=calls,
                    finish=r.choices[0].finish_reason, prompt_tokens=pt, completion_tokens=ct,
                    cost=cost, latency=lat)

class PplxResponses:
    BASE = "https://api.perplexity.ai/v1/responses"

    def __init__(self, model="openai/gpt-5.5", effort="medium", max_output_tokens=4000, timeout=300, retries=4):
        import requests
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}",
                               "Content-Type": "application/json"})
        self.model, self.effort, self.max_out, self.timeout, self.retries = model, effort, max_output_tokens, timeout, retries

    def ask(self, prompt, system=None, tag="", effort=None):
        body = dict(model=self.model, input=prompt, max_output_tokens=self.max_out)
        if system: body["instructions"] = system
        eff = effort or self.effort
        if eff: body["reasoning"] = dict(effort=eff)
        last = None
        for k in range(self.retries):
            t0 = time.time()
            try:
                r = self.s.post(self.BASE, json=body, timeout=self.timeout)
                if r.status_code == 200: break
                last = f"HTTP {r.status_code}: {r.text[:300]}"
            except Exception as e:
                last = e
            time.sleep(3 * (k + 1))
        else:
            raise RuntimeError(f"perplexity failed after {self.retries} tries: {last}")
        lat = time.time() - t0
        j = r.json()
        text = "".join(c.get("text", "") for it in j.get("output", []) if it.get("type") == "message"
                       for c in it.get("content", []) if isinstance(c, dict))
        u = j.get("usage", {}) or {}
        cost = float((u.get("cost") or {}).get("total_cost", 0.0))
        _log(dict(tag=tag, backend="pplx", model=self.model, prompt_tokens=u.get("input_tokens", 0),
                  completion_tokens=u.get("output_tokens", 0),
                  reasoning_tokens=(u.get("output_tokens_details") or {}).get("reasoning_tokens", 0),
                  cost_usd=cost, latency_s=round(lat, 2), status=j.get("status")))
        return dict(text=text, cost=cost, latency=lat, usage=u, status=j.get("status"))
