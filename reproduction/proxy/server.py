"""OpenAI chat.completions -> Perplexity Responses API proxy.

Why this exists: ChatDev 1.0 (openai SDK) and Magentic-One (AutoGen
OpenAIChatCompletionClient) both speak /v1/chat/completions, but Perplexity
serves gpt-5.4-mini ONLY via /v1/responses (chat.completions is Sonar-only).
This proxy lets both systems run unmodified: point OPENAI_BASE_URL at it.

Behavior (verified against the live API by probe_api.py, 2026-06-10):
- Any requested model name is aliased to TARGET_MODEL (default
  openai/gpt-5.4-mini). Native configs can keep saying "gpt-4o", which also
  keeps AutoGen's model_info (vision/function_calling) and ChatDev's
  tiktoken/ModelType tables happy with zero code changes.
- Tool calls round-trip: chat tools -> flat Responses tools; function_call /
  function_call_output items <-> assistant tool_calls / role=tool messages.
- Images pass through (input_image data URLs work on gpt-5.4-mini).
- response_format json_object -> text.format. stream=True is faked: one
  upstream call, replayed as SSE chunks.
- Every call is appended to calls.jsonl with tokens + exact cost (Perplexity
  returns usage.cost).

Run: conda run -n base python reproduction/proxy/server.py  [PROXY_PORT=8744]
"""
import json, os, threading, time

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for line in open(os.path.join(ROOT, '.env')):
    if '=' in line:
        k, v = line.strip().split('=', 1)
        os.environ.setdefault(k, v)

UPSTREAM = os.environ.get('PPLX_BASE', 'https://api.perplexity.ai/v1')
KEY = os.environ['PERPLEXITY_API_KEY']
TARGET_MODEL = os.environ.get('TARGET_MODEL', 'openai/gpt-5.4-mini')
PORT = int(os.environ.get('PROXY_PORT', '8744'))
LOG = os.path.join(HERE, 'calls.jsonl')
# Full wire-traffic dump (every request/response verbatim, images -> sha1
# stubs). This is the ground-truth trace: model-internal turns like the
# Magentic orchestrator's progress-ledger JSON never reach console logs, and
# losing them is what made the previous experiment's traces unjudgeable.
RAW = os.environ.get('PROXY_DUMP', os.path.join(HERE, 'raw_calls.jsonl'))
# Guardrails (2026-06-12): default per-call output cap when the caller sends
# none (all-time observed max reply is 2,564 tokens — 16k is ~6x headroom,
# bounds degenerate rambling; cap hits are visible as finish=length in
# calls.jsonl), and a cumulative per-proxy-session spend kill-switch
# (refuses calls past the budget; raise via SPEND_CAP=100 for judge runs).
OUT_TOKEN_CAP = int(os.environ.get('OUT_TOKEN_CAP', '16384'))
SPEND_CAP = float(os.environ.get('SPEND_CAP', '20'))
_spent = 0.0
_spent_lock = threading.Lock()
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
            # OpenAI chat.completions accepts content="" but Perplexity
            # Responses rejects it ("content cannot be empty"; hit by
            # MacNet's aggregation step) — a single space is the closest
            # accepted equivalent
            items.append(dict(role=out_role, content=content or ' '))
    return items, n_images


def to_responses_body(body):
    items, n_images = to_input_items(body.get('messages', []))
    # store=False removed 2026-06-12: Perplexity began rejecting the field
    # ("unknown field store", upstream 400 on every call)
    out = dict(model=TARGET_MODEL, input=items)
    # temperature/top_p/parallel_tool_calls dropped 2026-06-12: Perplexity's
    # Responses endpoint went schema-strict and 400s on them (probed
    # individually; max_output_tokens still accepted). Sampling params are
    # silently discarded — callers' temperature schedules are inert.
    for src, dst in (('max_tokens', 'max_output_tokens'),
                     ('max_completion_tokens', 'max_output_tokens')):
        if body.get(src) is not None:
            out[dst] = body[src]
    # ChatDev computes max_tokens = 4096 - tiktoken(prompt) for "gpt-4o"; once
    # the prompt outgrows that budget the value goes <= 0 and the API rejects
    # every retry. Drop the param instead (upstream default applies).
    if out.get('max_output_tokens') is not None and out['max_output_tokens'] < 16:
        del out['max_output_tokens']
    if out.get('max_output_tokens') is None:
        out['max_output_tokens'] = OUT_TOKEN_CAP
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


# /engines/{engine}/... is the path openai-python 0.x emits when called with
# engine= (DyLAN does this); engine is ignored — every model is aliased anyway.
@app.post('/t/{tag}/v1/engines/{engine}/chat/completions')
@app.post('/t/{tag}/engines/{engine}/chat/completions')
@app.post('/v1/engines/{engine}/chat/completions')
@app.post('/engines/{engine}/chat/completions')
@app.post('/t/{tag}/v1/chat/completions')
@app.post('/t/{tag}/chat/completions')
@app.post('/v1/chat/completions')
@app.post('/chat/completions')
async def chat(req: Request, tag: str = '', engine: str = ''):
    global _spent
    body = await req.json()
    with _spent_lock:
        if _spent >= SPEND_CAP:
            log_call(dict(ts=time.time(), tag=tag, error='spend_cap',
                          detail=f'session spend ${_spent:.2f} >= cap ${SPEND_CAP:.2f}'))
            return JSONResponse(status_code=402, content=dict(error=dict(
                message=f'proxy spend cap reached: ${_spent:.2f} of '
                        f'${SPEND_CAP:.2f} this session. Restart with '
                        f'SPEND_CAP=<n> to raise.',
                type='spend_cap', code=402)))
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
    if cost:
        with _spent_lock:
            _spent += cost
    log_call(dict(ts=t0, tag=tag, dur=round(dur, 2), model=body.get('model'),
                  prompt_tokens=resp['usage']['prompt_tokens'],
                  completion_tokens=resp['usage']['completion_tokens'],
                  cost=cost, n_msgs=len(body.get('messages', [])),
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
