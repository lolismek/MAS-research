"""Render each split4_openai input bundle to a compact markdown transcript a
subagent can read in one pass. Interleaves, per agent turn, the PRIVATE reasoning
summary that preceded each tool call (invisible to peers) with the tool call +
result and the single PUBLISHED message peers actually saw.

Output: analysis_openai/inputs_md/<uid8>.md
"""
import json, glob, os

HERE = os.path.dirname(os.path.abspath(__file__))
INP = os.path.join(HERE, 'inputs')
OUT = os.path.join(HERE, 'inputs_md')
RESULT_CAP = 900   # chars per tool result in the md transcript
REASON_CAP = 2000  # chars per reasoning summary (they're short anyway)


def trunc(s, n):
    s = s or ''
    return s if len(s) <= n else s[:n] + ' …[truncated]'


def render(b):
    L = [f"# Trace {b['uid8']}  ·  level {b['level']}  ·  category {b['category']}", '']
    L += ['## Task (verbatim prompt the team received)', '', b['question'], '']
    st = b['participation']['speaker_turns'] or {}
    L += ['## Gold answer & outcome',
          f"- **Expected (gold):** {b['expected_answer']}",
          f"- **Final answer the team produced:** {b['final_answer']}",
          f"- **Exact match:** {b['exact_match']}",
          f"- **Run:** {b['seconds']}s, rc={b.get('rc')}, agents that spoke={b['participation']['n_agents_spoke']}",
          f"- **Published turns per agent:** {st}", '']
    if b.get('no_data'):
        L += ['## NO DATA',
              'This run logged ZERO model calls (infra failure — the subprocess hung '
              'and was killed; no LLM activity to attribute). Treat as an '
              'infrastructure/harness failure, not a multi-agent dynamic.', '']
        if b.get('console_log_excerpt'):
            L += ['Console excerpt:', '```', b['console_log_excerpt'], '```']
        return '\n'.join(L)

    L += ['## How to read this',
          'The team is an AutoGen SelectorGroupChat. Each turn a **selector** LLM picks the '
          'next agent, then that agent runs a **private internal ReAct loop** — each round it '
          'emits a *reasoning summary* (shown below as `reasoning:`) and either calls tools or '
          'publishes. **Peers see ONLY the final published message**, never the reasoning or '
          'tool steps. The gap between private reasoning and the published message is where '
          'inter-agent misalignment (info distortion, ignored input, ToM failure, '
          'reasoning/action mismatch) lives.', '',
          '## Group-chat timeline', '']

    for i, t in enumerate(b['timeline']):
        sel = t['selector']
        head = f"### Turn {i+1} — Selector → {t['source']}"
        L += [head]
        if sel and sel.get('reasoning'):
            L += [f"- *selector reasoning:* {trunc(sel['reasoning'], REASON_CAP)}"]
        if sel and (sel.get('choice') or '') not in ('', t['source']):
            L += [f"- *selector raw choice string:* `{trunc(sel['choice'], 120)}`"]
        L += [f"**{t['source']}** — private loop, {t['n_internal_calls']} model round(s):", '']
        for j, rd in enumerate(t['rounds']):
            if rd['reasoning']:
                L += [f"- round {j+1} reasoning: {trunc(rd['reasoning'], REASON_CAP)}"]
            else:
                L += [f"- round {j+1}: (no reasoning summary emitted)"]
            for tl in rd['tools']:
                L += [f"    - 🔧 `{tl['name']}({trunc(tl['args'],200)})`",
                      f"      → result: {trunc(tl['result'], RESULT_CAP)}"]
            if rd['publish'] is not None:
                L += ['', '  **PUBLISHED to the group (peers see only this):**',
                      '  > ' + (rd['publish'] or '(empty)').replace('\n', '\n  > '), '']
        L += ['']
    return '\n'.join(L)


def main():
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for f in sorted(glob.glob(os.path.join(INP, '*.json'))):
        b = json.load(open(f))
        md = render(b)
        open(os.path.join(OUT, b['uid8'] + '.md'), 'w').write(md)
        n += 1
    print(f'wrote {n} markdown transcripts to {OUT}')
    # size report
    sizes = sorted(((os.path.getsize(os.path.join(OUT, x)), x)
                    for x in os.listdir(OUT)), reverse=True)
    for sz, x in sizes[:5]:
        print(f'  {sz/1024:6.0f} KB  {x}')


if __name__ == '__main__':
    main()
