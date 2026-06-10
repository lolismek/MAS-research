"""Smoke-test the proxy through the official openai SDK — the same protocol
surface ChatDev (plain chat, sampling params) and AutoGen/Magentic-One
(tools, images, json mode, streaming) will use.

Usage: start server.py first, then conda run -n base python smoke_proxy.py
"""
import base64, io, json, os, sys

from openai import OpenAI

PORT = int(os.environ.get('PROXY_PORT', '8744'))
client = OpenAI(base_url=f'http://127.0.0.1:{PORT}/v1', api_key='dummy')
fails = []


def check(name, ok, detail=''):
    print(f'[{"PASS" if ok else "FAIL"}] {name} {detail}')
    if not ok:
        fails.append(name)


# 1. plain multi-turn (ChatDev's whole protocol surface, plus sampling params)
r = client.chat.completions.create(model='gpt-4o', temperature=0.2, top_p=1.0,
                                   max_tokens=64, messages=[
    dict(role='system', content='Answer in exactly one word.'),
    dict(role='user', content='Color of the sky on a clear day?'),
    dict(role='assistant', content='Blue'),
    dict(role='user', content='And grass?')])
check('plain multi-turn', 'green' in r.choices[0].message.content.lower(),
      f'-> {r.choices[0].message.content!r} usage={r.usage.total_tokens}')

# 2. tool call + round-trip (AutoGen agents)
tools = [dict(type='function', function=dict(
    name='get_weather', description='Get weather for a city',
    parameters=dict(type='object', properties=dict(city=dict(type='string')),
                    required=['city'])))]
msgs = [dict(role='user', content='Weather in Paris? You must use the tool.')]
r = client.chat.completions.create(model='gpt-4o', tools=tools, messages=msgs)
tc = (r.choices[0].message.tool_calls or [None])[0]
check('tool call emitted', tc is not None and tc.function.name == 'get_weather',
      f'-> {tc and tc.function.arguments}')
if tc:
    msgs += [dict(role='assistant', content=r.choices[0].message.content,
                  tool_calls=[dict(id=tc.id, type='function',
                                   function=dict(name=tc.function.name,
                                                 arguments=tc.function.arguments))]),
             dict(role='tool', tool_call_id=tc.id,
                  content='{"temp_c": 18, "sky": "overcast"}')]
    r2 = client.chat.completions.create(model='gpt-4o', tools=tools, messages=msgs)
    check('tool round-trip', '18' in (r2.choices[0].message.content or ''),
          f'-> {r2.choices[0].message.content!r}')

# 3. image input (MultimodalWebSurfer screenshots)
from PIL import Image, ImageDraw
img = Image.new('RGB', (300, 200), (255, 140, 0))
ImageDraw.Draw(img).polygon([(150, 30), (50, 170), (250, 170)], fill=(0, 80, 255))
buf = io.BytesIO(); img.save(buf, format='PNG')
b64 = base64.b64encode(buf.getvalue()).decode()
r = client.chat.completions.create(model='gpt-4o', messages=[dict(role='user', content=[
    dict(type='text', text='One sentence: background color and shape color?'),
    dict(type='image_url', image_url=dict(url=f'data:image/png;base64,{b64}'))])])
txt = (r.choices[0].message.content or '').lower()
check('image passthrough', 'orange' in txt and 'blue' in txt, f'-> {txt!r}')

# 4. json mode (Magentic orchestrator ledger)
r = client.chat.completions.create(model='gpt-4o',
    response_format=dict(type='json_object'),
    messages=[dict(role='user', content='JSON object with key "answer" = "is_request_satisfied" as boolean false.')])
try:
    j = json.loads(r.choices[0].message.content)
    check('json mode', isinstance(j, dict), f'-> {r.choices[0].message.content!r}')
except Exception as e:
    check('json mode', False, str(e))

# 5. streaming (AutoGen create_stream path)
acc, n_chunks = '', 0
for ch in client.chat.completions.create(model='gpt-4o', stream=True,
        messages=[dict(role='user', content='Say exactly: STREAM OK')]):
    n_chunks += 1
    if ch.choices and ch.choices[0].delta.content:
        acc += ch.choices[0].delta.content
check('fake streaming', 'STREAM OK' in acc, f'-> {acc!r} ({n_chunks} chunks)')

# 6. legacy functions= API (older SDK callers)
r = client.chat.completions.create(model='gpt-4o',
    functions=[dict(name='get_weather', description='Get weather',
                    parameters=dict(type='object',
                                    properties=dict(city=dict(type='string'))))],
    messages=[dict(role='user', content='Weather in Rome? Use the function.')])
m = r.choices[0].message
check('legacy functions', bool(m.tool_calls or m.function_call),
      f'-> tool_calls={bool(m.tool_calls)}')

print('\n' + ('ALL PASS' if not fails else f'FAILURES: {fails}'))
sys.exit(1 if fails else 0)
