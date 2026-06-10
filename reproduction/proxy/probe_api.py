"""Probe Perplexity's Responses API for the exact shapes the chat-completions
proxy must translate. Run once before building/changing the proxy.

Usage: conda run -n base python reproduction/proxy/probe_api.py
"""
import json, os, sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for line in open(os.path.join(ROOT, '.env')):
    if '=' in line:
        k, v = line.strip().split('=', 1)
        os.environ.setdefault(k, v)

BASE = 'https://api.perplexity.ai/v1'
KEY = os.environ['PERPLEXITY_API_KEY']
MODEL = 'openai/gpt-5.4-mini'
HDRS = {'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'}


def post(body, label):
    r = requests.post(f'{BASE}/responses', headers=HDRS, json=body, timeout=120)
    print(f'\n=== {label} -> HTTP {r.status_code}')
    try:
        j = r.json()
    except Exception:
        print(r.text[:500]); return None
    print(json.dumps(j, indent=1)[:2500])
    return j


# 1. plain completion, multi-turn with system
post(dict(model=MODEL, store=False, input=[
    dict(role='system', content='You answer in exactly one word.'),
    dict(role='user', content='What color is the sky on a clear day?'),
    dict(role='assistant', content='Blue'),
    dict(role='user', content='And grass?'),
]), 'plain multi-turn')

# 2. tool call request
TOOLS = [dict(type='function', name='get_weather',
              description='Get current weather for a city',
              parameters=dict(type='object',
                              properties=dict(city=dict(type='string')),
                              required=['city']))]
j = post(dict(model=MODEL, store=False, tools=TOOLS,
              input=[dict(role='user', content='Weather in Paris? Use the tool.')]),
         'tool call')

# 3. tool result round-trip
if j:
    fc = next((o for o in j.get('output', []) if o.get('type') == 'function_call'), None)
    if fc:
        post(dict(model=MODEL, store=False, tools=TOOLS, input=[
            dict(role='user', content='Weather in Paris? Use the tool.'),
            dict(type='function_call', call_id=fc['call_id'], name=fc['name'],
                 arguments=fc['arguments']),
            dict(type='function_call_output', call_id=fc['call_id'],
                 output='{"temp_c": 18, "sky": "overcast"}'),
        ]), 'tool round-trip')

# 4. JSON mode
post(dict(model=MODEL, store=False,
          text=dict(format=dict(type='json_object')),
          input=[dict(role='user', content='Give me a JSON object with keys a=1, b=2.')]),
     'json_object format')

# 5. image input (expected to be rejected)
post(dict(model=MODEL, store=False, input=[
    dict(role='user', content=[
        dict(type='input_text', text='What is in this image?'),
        dict(type='input_image',
             image_url='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='),
    ])]), 'image input (expect reject)')

# 6. sampling params tolerance (chat.completions senders pass these)
post(dict(model=MODEL, store=False, temperature=0.2, top_p=1.0, max_output_tokens=64,
          input=[dict(role='user', content='Say OK.')]), 'sampling params')
