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
_log_lock = threading.Lock()
_raw_lock = threading.Lock()

# Two upstream backends, selected per-request by route prefix:
#   /t/<tag>/...  -> PPLX   (Perplexity reselling openai/gpt-5.4-mini; NO reasoning
#                            item is ever returned — verified, it's stripped upstream)
#   /o/<tag>/...  -> OPENAI (OpenAI direct; with reasoning.summary set, /responses
#                            returns a reasoning summary item, even on tool-call turns)
# The reasoning summary is captured into raw_calls.jsonl (the trace source) so the
# per-turn "what the model was thinking before it acted" gap becomes observable.
PPLX = dict(name='pplx', base=UPSTREAM, key=KEY, model=TARGET_MODEL, reasoning=None)
OPENAI = dict(
    name='openai',
    base=os.environ.get('OPENAI_BASE', 'https://api.openai.com/v1'),
    key=os.environ.get('OPENAI_API_KEY', ''),
    model=os.environ.get('OPENAI_MODEL', 'gpt-5.4-mini'),
    reasoning=dict(summary=os.environ.get('REASONING_SUMMARY', 'detailed'),
                   effort=os.environ.get('REASONING_EFFORT', 'low')))


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


def to_responses_body(body, backend, tag=''):
    items, n_images = to_input_items(body.get('messages', []))
    # NB: do NOT send `store` — Perplexity's /responses rejects it as an unknown
    # field ("invalid request body: json: unknown field \"store\"").
    out = dict(model=backend['model'], input=items)
    # OpenAI direct: ask for a reasoning summary (Perplexity has reasoning=None and
    # rejects the summary field, so this is OpenAI-only).
    if backend.get('reasoning'):
        out['reasoning'] = dict(backend['reasoning'])
    for src, dst in (('temperature', 'temperature'), ('top_p', 'top_p'),
                     ('max_tokens', 'max_output_tokens'),
                     ('max_completion_tokens', 'max_output_tokens'),
                     ('parallel_tool_calls', 'parallel_tool_calls')):
        if body.get(src) is not None:
            out[dst] = body[src]
    # ChatDev sets max_tokens = num_max_token_map["gpt-4o"](=4096) - tiktoken(prompt)
    # on EVERY call (camel/model_backend.py). That budget is a stale gpt-4o-era
    # constant, not a meaningful limit: as the dialogue accumulates the codebase the
    # residual shrinks, so late phases (CodeReviewModification, Manual) get only a
    # few hundred tokens and the more-verbose gpt-5.4-mini is cut off MID-LINE -- a
    # systemic truncation source the trace judge misreads as inter-agent failure
    # (ChatDev judging confound "A"). ChatDev runs are tagged /t/cd_*, so drop the
    # cap entirely for them (the model-max default applies). For the other systems
    # (Magentic/AutoGen) keep their cap, but still drop a non-positive value, which
    # the API would otherwise 400 on in a fatal retry loop.
    cap = out.get('max_output_tokens')
    if cap is not None and (tag.startswith('cd_') or cap < 16):
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
    # NB: do NOT send `tool_choice` — Perplexity's /responses rejects it
    # ("unknown field tool_choice"); the model picks tools on its own (== auto,
    # which is what WebSurfer/the orchestrator request anyway).
    # NB: do NOT translate response_format -> text.format. Perplexity's
    # /responses rejects the `format` field ("invalid request body: json:
    # unknown field \"format\""). Callers that need JSON (e.g. the Magentic-One
    # orchestrator, json_output=True) enforce it via their prompt, so dropping
    # the structured-output hint is safe for this reproduction.
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
def _unknown_field(text):
    """Name of the field Perplexity rejected, from a 400 body, else None."""
    import re
    try:
        p = json.loads(text).get('error', {}).get('param')
        if p:
            return p
    except Exception:
        pass
    m = re.search(r'unknown field \\?"([^"\\]+)\\?"', text)
    return m.group(1) if m else None


def call_upstream(rbody, backend):
    rbody = dict(rbody)  # local copy; we may strip drifted fields below
    last = None
    for attempt in range(8):
        try:
            r = requests.post(f"{backend['base']}/responses", json=rbody, timeout=600,
                              headers={'Authorization': f"Bearer {backend['key']}"})
        except requests.RequestException as e:
            last = (599, str(e))
            time.sleep(2 ** (attempt + 1))
            continue
        if r.status_code == 200:
            return 200, r.json()
        last = (r.status_code, r.text[:2000])
        # Perplexity's /responses has tightened over time and 400s on fields the
        # OpenAI schema permits (store, tool_choice, ...). Auto-heal: strip the
        # named top-level unknown field and retry instead of failing the call.
        if r.status_code == 400:
            fld = _unknown_field(r.text)
            if fld and fld in rbody:
                rbody.pop(fld, None)
                continue
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


def _reasoning_summary(j):
    """Join any reasoning-summary text from an OpenAI /responses body. Perplexity
    never returns reasoning items; OpenAI does when reasoning.summary is set —
    including on tool-call turns (the pre-action 'thinking' we otherwise can't see)."""
    texts = []
    for o in j.get('output', []):
        if o.get('type') == 'reasoning':
            for s in o.get('summary', []) or []:
                if s.get('type') == 'summary_text' and s.get('text'):
                    texts.append(s['text'])
    return '\n\n'.join(texts) or None


@app.post('/t/{tag}/v1/chat/completions')
@app.post('/t/{tag}/chat/completions')
@app.post('/v1/chat/completions')
@app.post('/chat/completions')
async def chat(req: Request, tag: str = ''):
    return await _handle(req, tag, PPLX)


@app.post('/o/{tag}/v1/chat/completions')
@app.post('/o/{tag}/chat/completions')
@app.post('/o/v1/chat/completions')
@app.post('/o/chat/completions')
async def chat_openai(req: Request, tag: str = ''):
    return await _handle(req, tag, OPENAI)


async def _handle(req: Request, tag: str, backend: dict):
    body = await req.json()
    rbody, n_images = to_responses_body(body, backend, tag)
    t0 = time.time()
    status, j = call_upstream(rbody, backend)
    dur = time.time() - t0
    if status != 200:
        log_call(dict(ts=t0, tag=tag, backend=backend['name'], dur=round(dur, 2),
                      error=status, detail=str(j)[:300]))
        return JSONResponse(status_code=status if isinstance(status, int) else 500,
                            content=dict(error=dict(
                                message=f'upstream {status}: {j}',
                                type='upstream_error', code=status)))
    resp = from_responses_body(j, body.get('model', backend['model']),
                               rbody.get('max_output_tokens'))
    reasoning = _reasoning_summary(j)
    with _raw_lock, open(RAW, 'a') as f:
        f.write(json.dumps(dict(
            ts=t0, tag=tag, backend=backend['name'],
            messages=_redact_images(body.get('messages', [])),
            tools=[t.get('function', t).get('name')
                   for t in body.get('tools') or []],
            response_format=body.get('response_format'),
            reasoning=reasoning,
            reply=resp['choices'][0]['message'])) + '\n')
    cost = ((j.get('usage') or {}).get('cost') or {}).get('total_cost')
    log_call(dict(ts=t0, tag=tag, backend=backend['name'], dur=round(dur, 2),
                  model=body.get('model'),
                  prompt_tokens=resp['usage']['prompt_tokens'],
                  completion_tokens=resp['usage']['completion_tokens'],
                  cost=cost, n_msgs=len(body.get('messages', [])),
                  n_images=n_images, tools=bool(rbody.get('tools')),
                  has_reasoning=bool(reasoning),
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
