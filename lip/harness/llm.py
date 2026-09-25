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
# $/M prompt, $/M completion: Tinker list prices (tinker-docs .../tinker/models/, read 2026-09-24). Cached prefill is
# billed at 20% of prefill, which we can't see in the API response, so logged costs are an upper bound on the bill.
# Calls logged before 2026-09-24 used older rates (Qwen3.6 0.36/0.89, Qwen3.5-397B 2/6); list_cost() re-prices them.
TINKER_RATES = {"Qwen/Qwen3.6-35B-A3B": (0.54, 1.335),
                "openai/gpt-oss-120b": (0.33, 0.84),
                "openai/gpt-oss-120b:peft:131072": (0.78, 1.94),
                "Qwen/Qwen3.5-397B-A17B": (3.00, 7.50),
                "Qwen/Qwen3.5-397B-A17B:peft:262144": (4.00, 10.00)}
TINKER_RATE_UNKNOWN = (7.48, 18.72)   # unlisted model: the priciest listed rate (Inkling 256K), so caps err on the safe side

def list_cost(rec):
    """a logged call's cost re-priced at the current TINKER_RATES (tinker calls with token counts), else its logged cost."""
    if rec.get("backend") != "tinker" or not (rec.get("prompt_tokens") or rec.get("completion_tokens")):
        return rec.get("cost_usd", 0.0) or 0.0
    pr, cr = TINKER_RATES.get(rec.get("model"), TINKER_RATE_UNKNOWN)
    return ((rec.get("prompt_tokens") or 0) * pr + (rec.get("completion_tokens") or 0) * cr) / 1e6

HARD_CAP = float(os.environ.get("LIP_HARD_CAP", "0") or 0)   # total logged USD; 0 = no cap
_cache = dict(t=0.0, file=0.0, delta=0.0)   # cached file total + costs logged by this process since the last read
_SPEND_REFRESH = 20.0

class BudgetExceeded(RuntimeError):
    pass

class ContextTooLong(RuntimeError):
    pass


def _log(rec):
    rec = dict(ts=time.time(), **rec)
    if SESSION: rec["session"] = SESSION
    with _log_lock:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as f: f.write(json.dumps(rec) + "\n")
        _cache["delta"] += rec.get("cost_usd", 0.0) or 0.0
        if SESSION: _sess_cache["delta"] += rec.get("cost_usd", 0.0) or 0.0

def _read_log(tag_prefix=None):
    tot = 0.0
    if not os.path.exists(LOG_PATH): return 0.0
    for line in open(LOG_PATH):
        try: r = json.loads(line)
        except Exception: continue          # partial line from a concurrent writer
        # per-experiment totals are re-priced at current rates; the global total (shared CAP file) keeps logged costs
        if tag_prefix is None: tot += r.get("cost_usd", 0.0) or 0.0
        elif str(r.get("tag", "")).startswith(tag_prefix): tot += list_cost(r)
    return tot

def spend(tag_prefix=None, fresh=False):
    """Total USD in the log (optionally only tags starting with tag_prefix). The untagged total is cached for
    _SPEND_REFRESH seconds and advanced by this process's own logged costs in between (other processes appending
    to the same log are picked up at the next refresh)."""
    if tag_prefix is not None: return _read_log(tag_prefix)
    with _log_lock:
        if fresh or time.time() - _cache["t"] > _SPEND_REFRESH:
            _cache.update(t=time.time(), file=_read_log(), delta=0.0)
        return _cache["file"] + _cache["delta"]

CAP_FILE = os.path.join(ROOT, "lip", "traces", "batch", "CAP")   # a number in this file overrides LIP_HARD_CAP (live)

def current_cap():
    try: return float(open(CAP_FILE).read().strip())
    except Exception: return HARD_CAP

# Per-experiment cap: LIP_EXP_PREFIX=int2 LIP_EXP_CAP=30 -> stop once calls tagged "<prefix>..." or "judge/<prefix>..." reach the cap
EXP_PREFIX = os.environ.get("LIP_EXP_PREFIX") or None
EXP_CAP = float(os.environ.get("LIP_EXP_CAP", "0") or 0)
_exp_cache = dict(t=0.0, v=0.0)

def exp_spend():
    if not EXP_PREFIX or not os.path.exists(LOG_PATH): return 0.0
    with _log_lock:
        if time.time() - _exp_cache["t"] > _SPEND_REFRESH:
            tot = 0.0
            for line in open(LOG_PATH):
                if EXP_PREFIX not in line: continue
                try: r = json.loads(line)
                except Exception: continue
                tg = str(r.get("tag", ""))
                if tg.startswith(EXP_PREFIX) or tg.startswith("judge/" + EXP_PREFIX): tot += list_cost(r)
            _exp_cache.update(t=time.time(), v=tot)
        return _exp_cache["v"]

def exp_spent():
    return bool(EXP_PREFIX and EXP_CAP and exp_spend() >= EXP_CAP)

# Per-session cap: LIP_SESSION=<id> LIP_SESSION_CAP=200 -> every call logged by a process with this LIP_SESSION carries
# session=<id>; once those calls reach the cap, traces/sessions/<id>.STOP is written and every later call (any process
# of the session) raises BudgetExceeded. Calls from other sessions never count. session_watchdog.sh is the backstop.
SESSION = os.environ.get("LIP_SESSION") or None
SESSION_CAP = float(os.environ.get("LIP_SESSION_CAP", "0") or 0)
SESSION_DIR = os.path.join(ROOT, "lip", "traces", "sessions")
_sess_cache = dict(t=0.0, file=0.0, delta=0.0)
if SESSION:
    os.makedirs(SESSION_DIR, exist_ok=True)
    with open(os.path.join(SESSION_DIR, f"{SESSION}.pids"), "a") as f: f.write(f"{os.getpid()}\n")

def session_stop_path(session=None):
    return os.path.join(SESSION_DIR, f"{session or SESSION}.STOP")

def session_spend(session=None, fresh=False):
    """USD logged by calls tagged with this session (cached 10 s, advanced by this process's own calls in between)."""
    s = session or SESSION
    if not s or not os.path.exists(LOG_PATH): return 0.0
    def read():
        tot = 0.0
        for line in open(LOG_PATH):
            if s not in line: continue
            try: r = json.loads(line)
            except Exception: continue
            if r.get("session") == s: tot += r.get("cost_usd", 0.0) or 0.0
        return tot
    if session and session != SESSION: return read()
    with _log_lock:
        if fresh or time.time() - _sess_cache["t"] > 10.0:
            _sess_cache.update(t=time.time(), file=read(), delta=0.0)
        return _sess_cache["file"] + _sess_cache["delta"]

def check_cap(tag=""):
    """Raise BudgetExceeded if the session cap, the hard cap (total logged USD; CAP file, else LIP_HARD_CAP) or the
    experiment cap is reached."""
    if SESSION:
        if os.path.exists(session_stop_path()):
            raise BudgetExceeded(f"session '{SESSION}' stopped ({session_stop_path()} exists) at {tag}")
        if SESSION_CAP and session_spend() >= SESSION_CAP:
            with open(session_stop_path(), "w") as f: f.write(f"{session_spend():.2f} >= {SESSION_CAP:.2f} at {time.ctime()}\n")
            raise BudgetExceeded(f"session cap ${SESSION_CAP:.2f} on '{SESSION}' reached (${session_spend():.2f}) at {tag}")
    cap = None if SESSION else current_cap()   # a session counts only its own calls, not the shared-log total
    if cap and spend() >= cap:
        raise BudgetExceeded(f"hard cap ${cap:.2f} reached (spend ${spend():.2f}) at {tag}")
    if exp_spent():
        raise BudgetExceeded(f"experiment cap ${EXP_CAP:.2f} on '{EXP_PREFIX}' reached (${exp_spend():.2f}) at {tag}")

# ---------------------------------------------------------------- Qwen XML tool calls
_TC = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.S)
_FN = re.compile(r"<function=([\w.-]+)>?(.*?)</function>", re.S)
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
    lines = ["# Tools", "You may call tools. To call one, emit exactly this XML (one call per turn), with the function's",
             "real name and parameter names, for example:",
             "<tool_call>", "<function=search>", "<parameter=query>first ladies of the United States</parameter>", "</function>", "</tool_call>",
             "", "Available functions:"]
    for t in tools:
        f = t["function"] if "function" in t else t
        props = f.get("parameters", {}).get("properties", {})
        sig = ", ".join(f"{k}: {v.get('type','string')}" + (f" — {v['description']}" if v.get("description") else "")
                        for k, v in props.items())
        lines.append(f"- {f['name']}({sig}): {f.get('description','')}")
    return "\n".join(lines)

class TinkerChat:
    def __init__(self, model=TINKER_MODEL, max_tokens=12000, timeout=150, retries=None):
        from openai import OpenAI
        retries = retries or int(os.environ.get("LIP_TINKER_RETRIES", "8"))   # 429s are account-wide (shared lab account)
        self.c = OpenAI(api_key=os.environ["TINKER_API_KEY"], base_url=TINKER_BASE, timeout=timeout, max_retries=0)
        self.model, self.max_tokens, self.retries = model, max_tokens, retries

    def chat(self, messages, tag="", temperature=None, max_tokens=None):
        """messages: plain OpenAI-style dicts (system/user/assistant text only).
        Returns dict(reasoning, content, tool_calls, finish, usage, cost, latency)."""
        kw = dict(model=self.model, messages=messages, max_tokens=max_tokens or self.max_tokens)
        if temperature is not None: kw["temperature"] = temperature
        last = None
        for k in range(self.retries):
            check_cap(tag)
            t0 = time.time()
            try:
                r = self.c.chat.completions.create(**kw); break
            except Exception as e:
                last = e
                if "context window" in str(e): raise ContextTooLong(str(e)[:300])   # retrying can't help
                _log(dict(tag=tag, backend="tinker", model=self.model, prompt_tokens=0, completion_tokens=0, cost_usd=0.0,
                          latency_s=round(time.time() - t0, 2), finish="error", error=str(e)[:200], attempt=k))
                time.sleep(min(60, 3 * 2 ** k))     # 3, 6, 12, 24, 48, then 60 s per try (capacity / rate-limit errors)
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
        pr, cr = TINKER_RATES.get(self.model, TINKER_RATE_UNKNOWN)
        cost = (pt * pr + ct * cr) / 1e6
        _log(dict(tag=tag, backend="tinker", model=self.model, prompt_tokens=pt, completion_tokens=ct,
                  cost_usd=cost, latency_s=round(lat, 2), finish=r.choices[0].finish_reason))
        return dict(reasoning=reasoning, content=clean, raw_content=content, tool_calls=calls,
                    finish=r.choices[0].finish_reason, prompt_tokens=pt, completion_tokens=ct,
                    cost=cost, latency=lat)

class PplxResponses:
    BASE = "https://api.perplexity.ai/v1/responses"

    def __init__(self, model="openai/gpt-5.5", effort="medium", max_output_tokens=4000, timeout=300, retries=6):
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
            check_cap(tag)
            t0 = time.time()
            try:
                r = self.s.post(self.BASE, json=body, timeout=self.timeout)
                if r.status_code == 200: break
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                _log(dict(tag=tag, backend="pplx", model=self.model, prompt_tokens=0, completion_tokens=0, cost_usd=0.0,
                          latency_s=round(time.time() - t0, 2), status="error", error=last[:200], attempt=k))
                if r.status_code in (401, 403): raise RuntimeError(f"perplexity auth/quota error, not retrying: {last}")
            except Exception as e:
                last = e
                _log(dict(tag=tag, backend="pplx", model=self.model, prompt_tokens=0, completion_tokens=0, cost_usd=0.0,
                          latency_s=round(time.time() - t0, 2), status="error", error=str(e)[:200], attempt=k))
            time.sleep(min(60, 3 * 2 ** k))
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
