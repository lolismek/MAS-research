"""OpenAI chat.completions -> Perplexity Responses API proxy.

Vendored from origin/main:reproduction/proxy/server.py (validated 2026-06-10
against the live API; smoke_proxy.py 7/7). Perplexity serves gpt-5.4-mini
ONLY via /v1/responses -- chat.completions is Sonar-only -- so mini-CORAL's
APIEngine points at this proxy instead of api.perplexity.ai directly.

Local changes vs main:
- .env is loaded from the repo root if present, else PERPLEXITY_API_KEY must
  already be in the environment (this worktree has no .env).
- calls.jsonl / raw_calls.jsonl land in PROXY_LOG_DIR (default
  <root>/proxy_logs/); scripts/cost_watch.py reads calls.jsonl for live spend
  (Perplexity returns usage.cost -> exact dollars per call).
- Zero-usage workaround (observed 2026-06-11): Perplexity returns an all-zero
  usage block whenever the response output is a function_call -- i.e. on most
  calls of an agentic run. When that happens the proxy estimates tokens
  (chars/4) and prices them at EST_IN_PER_M / EST_OUT_PER_M dollars per
  million (defaults 0.75 / 4.50, calibrated against a non-tool call the same
  day); such records carry "estimated": true in calls.jsonl.

Run: python scripts/pplx_proxy.py   [PROXY_PORT=8744 TARGET_MODEL=openai/gpt-5.4-mini]
"""
import json, os, sys, threading, time

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if os.path.exists(os.path.join(ROOT, '.env')):
    for line in open(os.path.join(ROOT, '.env')):
        if '=' in line:
            k, v = line.strip().split('=', 1)
            os.environ.setdefault(k, v)

UPSTREAM = os.environ.get('PPLX_BASE', 'https://api.perplexity.ai/v1')
KEY = os.environ.get('PERPLEXITY_API_KEY')
if not KEY:
    sys.exit('PERPLEXITY_API_KEY not set (export it or put a .env at repo root)')
TARGET_MODEL = os.environ.get('TARGET_MODEL', 'openai/gpt-5.4-mini')
PORT = int(os.environ.get('PROXY_PORT', '8744'))
LOG_DIR = os.environ.get('PROXY_LOG_DIR', os.path.join(ROOT, 'proxy_logs'))
os.makedirs(LOG_DIR, exist_ok=True)
LOG = os.path.join(LOG_DIR, 'calls.jsonl')
# Full wire-traffic dump (every request/response verbatim, images -> sha1
# stubs). Ground-truth trace of every model-internal turn.
RAW = os.environ.get('PROXY_DUMP', os.path.join(LOG_DIR, 'raw_calls.jsonl'))
EST_IN_PER_M = float(os.environ.get('EST_IN_PER_M', '0.75'))
EST_OUT_PER_M = float(os.environ.get('EST_OUT_PER_M', '4.50'))
_log_lock = threading.Lock()
_raw_lock = threading.Lock()


def _redact_images(messages):
    """Copy messages with image payloads replaced by '<image sha1 ...>' stubs."""
    import hashlib
    out = []
    for m in messages:
        c = m.get('content')
        if not isinstance(c, list):
            out.append(m)
            continue
        parts = []
        for p in c:
            if isinstance(p, dict) and p.get('type') == 'image_url':
                iu = p.get('image_url')
                url = iu.get('url') if isinstance(iu, dict) else (iu or '')
                if url.startswith('data:'):
                    h = hashlib.sha1(url.encode()).hexdigest()[:12]
                    p = dict(type='image_url',
                             image_url=f'<image {len(url)}B sha1:{h}>')
            parts.append(p)
        out.append({**m, 'content': parts})
    return out

app = FastAPI()


# ------------------------------------------------------- request mapping ----
def _text_of(content):
    """Flatten a chat.completions content field to plain text."""
    if content is None:
        return ''
    if isinstance(content, str):
        return content
    return '\n'.join(p.get('text', '') for p in content
                     if isinstance(p, dict) and p.get('type') == 'text')


def to_input_items(messages):
    items, n_images = [], 0
    for m in messages:
        role = m.get('role')
        if role == 'tool':
            items.append(dict(type='function_call_output',
                              call_id=m.get('tool_call_id', ''),
                              output=_text_of(m.get('content'))))
            continue
        if role == 'assistant':
            txt = _text_of(m.get('content'))
            if txt:
                items.append(dict(role='assistant', content=txt))
            for tc in m.get('tool_calls') or []:
                items.append(dict(type='function_call', call_id=tc['id'],
                                  name=tc['function']['name'],
                                  arguments=tc['function']['arguments']))
            continue
        # system / developer / user
        out_role = {'developer': 'system'}.get(role, role)
        content = m.get('content')
        if isinstance(content, list):
            parts = []
            for p in content:
                if not isinstance(p, dict):
                    continue
                if p.get('type') == 'text':
                    parts.append(dict(type='input_text', text=p.get('text', '')))
                elif p.get('type') == 'image_url':
                    iu = p.get('image_url')
                    url = iu.get('url') if isinstance(iu, dict) else iu
                    parts.append(dict(type='input_image', image_url=url))
                    n_images += 1
            items.append(dict(role=out_role, content=parts))
        else:
            items.append(dict(role=out_role, content=content or ''))
    return items, n_images


def to_responses_body(body):
    items, n_images = to_input_items(body.get('messages', []))
    out = dict(model=TARGET_MODEL, store=False, input=items)
    for src, dst in (('temperature', 'temperature'), ('top_p', 'top_p'),
                     ('max_tokens', 'max_output_tokens'),
                     ('max_completion_tokens', 'max_output_tokens'),
                     ('parallel_tool_calls', 'parallel_tool_calls')):
        if body.get(src) is not None:
            out[dst] = body[src]
    # Senders that compute max_tokens = budget - tiktoken(prompt) can go <= 0
    # once the prompt outgrows the budget; the API rejects every retry then.
    # Drop the param instead (upstream default applies).
    if out.get('max_output_tokens') is not None and out['max_output_tokens'] < 16:
        del out['max_output_tokens']
    tools = []
    for t in body.get('tools') or []:
        if t.get('type') == 'function':
            f = t.get('function', {})
            tools.append(dict(type='function', name=f.get('name'),
                              description=f.get('description', ''),
                              parameters=f.get('parameters')
                              or dict(type='object', properties={})))
    # legacy functions= API (older openai SDKs)
    for f in body.get('functions') or []:
        tools.append(dict(type='function', name=f.get('name'),
                          description=f.get('description', ''),
                          parameters=f.get('parameters')
                          or dict(type='object', properties={})))
    if tools:
        out['tools'] = tools
    tc = body.get('tool_choice')
    if isinstance(tc, str) and tc in ('auto', 'none', 'required'):
        out['tool_choice'] = tc
    elif isinstance(tc, dict) and tc.get('type') == 'function':
        out['tool_choice'] = dict(type='function',
                                  name=tc.get('function', {}).get('name'))
    rf = body.get('response_format')
    if isinstance(rf, dict) and rf.get('type') in ('json_object', 'json_schema'):
        fmt = dict(type=rf['type'])
        if rf.get('type') == 'json_schema':
            js = rf.get('json_schema', {})
            fmt.update(name=js.get('name', 'response'), schema=js.get('schema', {}))
            if js.get('strict') is not None:
                fmt['strict'] = js['strict']
        out['text'] = dict(format=fmt)
    return out, n_images


# ------------------------------------------------------ response mapping ----
def from_responses_body(j, req_model, max_out=None):
    texts, tool_calls = [], []
    for o in j.get('output', []):
        if o.get('type') == 'message':
            texts += [c.get('text', '') for c in o.get('content', [])
                      if c.get('type') == 'output_text']
        elif o.get('type') == 'function_call':
            tool_calls.append(dict(id=o.get('call_id'), type='function',
                                   function=dict(name=o.get('name'),
                                                 arguments=o.get('arguments', '{}'))))
    msg = dict(role='assistant', content=('\n'.join(texts) if texts else None))
    u = j.get('usage') or {}
    if tool_calls:
        msg['tool_calls'] = tool_calls
        finish = 'tool_calls'
    elif (j.get('incomplete_details') or {}).get('reason') == 'max_output_tokens':
        finish = 'length'
    elif max_out is not None and (u.get('output_tokens') or 0) >= max_out:
        # Perplexity reports status=completed/incomplete_details=None even
        # when max_output_tokens truncates the response (verified 2026-06-10),
        # so detect cap-hits from the token count ourselves.
        finish = 'length'
    else:
        finish = 'stop'
    usage = dict(prompt_tokens=u.get('input_tokens', 0),
                 completion_tokens=u.get('output_tokens', 0),
                 total_tokens=u.get('total_tokens', 0))
    # echo the dated snapshot name AutoGen resolves "gpt-4o" to, else every
    # run starts with repeated "Resolved model mismatch" warnings in the trace
    echo_model = 'gpt-4o-2024-08-06' if req_model == 'gpt-4o' else req_model
    return dict(id='chatcmpl-' + j.get('id', 'x'), object='chat.completion',
                created=int(time.time()), model=echo_model,
                choices=[dict(index=0, message=msg, finish_reason=finish,
                              logprobs=None)],
                usage=usage)


# --------------------------------------------------------------- upstream ----
def call_upstream(rbody):
    last = None
    for attempt in range(5):
        try:
            r = requests.post(f'{UPSTREAM}/responses', json=rbody, timeout=600,
                              headers={'Authorization': f'Bearer {KEY}'})
        except requests.RequestException as e:
            last = (599, str(e))
            time.sleep(2 ** (attempt + 1))
            continue
        if r.status_code == 200:
            return 200, r.json()
        last = (r.status_code, r.text[:2000])
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** (attempt + 1))
            continue
        break
    return last


def log_call(rec):
    with _log_lock, open(LOG, 'a') as f:
        f.write(json.dumps(rec) + '\n')


# -------------------------------------------------------------- endpoints ----
@app.get('/v1/models')
@app.get('/models')
def models():
    return dict(object='list', data=[dict(id=m, object='model', created=0,
                                          owned_by='proxy')
                                     for m in ('gpt-4o', 'gpt-4o-mini',
                                               TARGET_MODEL)])


@app.post('/t/{tag}/v1/chat/completions')
@app.post('/t/{tag}/chat/completions')
@app.post('/v1/chat/completions')
@app.post('/chat/completions')
async def chat(req: Request, tag: str = ''):
    body = await req.json()
    rbody, n_images = to_responses_body(body)
    t0 = time.time()
    status, j = call_upstream(rbody)
    dur = time.time() - t0
    if status != 200:
        log_call(dict(ts=t0, tag=tag, dur=round(dur, 2), error=status,
                      detail=str(j)[:300]))
        return JSONResponse(status_code=status if isinstance(status, int) else 500,
                            content=dict(error=dict(
                                message=f'upstream {status}: {j}',
                                type='upstream_error', code=status)))
    resp = from_responses_body(j, body.get('model', TARGET_MODEL),
                               rbody.get('max_output_tokens'))
    with _raw_lock, open(RAW, 'a') as f:
        f.write(json.dumps(dict(
            ts=t0, tag=tag, messages=_redact_images(body.get('messages', [])),
            tools=[t.get('function', t).get('name')
                   for t in body.get('tools') or []],
            response_format=body.get('response_format'),
            reply=resp['choices'][0]['message'])) + '\n')
    cost = ((j.get('usage') or {}).get('cost') or {}).get('total_cost')
    estimated = False
    if resp['usage']['total_tokens'] == 0:
        # Perplexity zero-usage quirk on function_call outputs: estimate.
        msg = resp['choices'][0]['message']
        out_chars = len(msg.get('content') or '') + sum(
            len(tc['function']['name']) + len(tc['function']['arguments'])
            for tc in msg.get('tool_calls') or [])
        pt = len(json.dumps(rbody.get('input', []))) // 4 \
            + len(json.dumps(rbody.get('tools', []))) // 4
        ct = max(out_chars // 4, 1)
        resp['usage'] = dict(prompt_tokens=pt, completion_tokens=ct,
                             total_tokens=pt + ct)
        cost = pt * EST_IN_PER_M / 1e6 + ct * EST_OUT_PER_M / 1e6
        estimated = True
    log_call(dict(ts=t0, tag=tag, dur=round(dur, 2), model=body.get('model'),
                  prompt_tokens=resp['usage']['prompt_tokens'],
                  completion_tokens=resp['usage']['completion_tokens'],
                  cost=cost, estimated=estimated,
                  n_msgs=len(body.get('messages', [])),
                  n_images=n_images, tools=bool(rbody.get('tools')),
                  finish=resp['choices'][0]['finish_reason'],
                  stream=bool(body.get('stream'))))

    if not body.get('stream'):
        return JSONResponse(content=resp)

    # fake streaming: replay the complete response as SSE chunks
    def sse():
        base = dict(id=resp['id'], object='chat.completion.chunk',
                    created=resp['created'], model=resp['model'])
        msg = resp['choices'][0]['message']
        chunks = [dict(**base, choices=[dict(index=0, delta=dict(role='assistant'),
                                             finish_reason=None)])]
        if msg.get('content'):
            chunks.append(dict(**base, choices=[dict(
                index=0, delta=dict(content=msg['content']), finish_reason=None)]))
        for i, tc in enumerate(msg.get('tool_calls') or []):
            chunks.append(dict(**base, choices=[dict(
                index=0, delta=dict(tool_calls=[dict(index=i, id=tc['id'],
                                                     type='function',
                                                     function=tc['function'])]),
                finish_reason=None)]))
        chunks.append(dict(**base, choices=[dict(
            index=0, delta={}, finish_reason=resp['choices'][0]['finish_reason'])]))
        if (body.get('stream_options') or {}).get('include_usage'):
            chunks.append(dict(**base, choices=[], usage=resp['usage']))
        for c in chunks:
            yield f'data: {json.dumps(c)}\n\n'
        yield 'data: [DONE]\n\n'

    return StreamingResponse(sse(), media_type='text/event-stream')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=PORT, log_level='warning')
