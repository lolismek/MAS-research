"""Build a single traces.json for the split4 trace viewer.

For each split4 run it reconstructs the timeline the way the topology actually works:
the SelectorGroupChat routes via a selector LLM call (wire_log row with one message
containing the selector prompt; its reply is the chosen member), then the chosen agent
runs a PRIVATE internal ReAct loop (a run of wire_log rows whose messages accumulate
tool calls + results); the LAST row of that run carries the full private context and the
agent's published `reply`. Peers see only that published reply — the viewer makes the
gap between the private loop and the published message visible, and lets you inspect the
selector's routing context for every turn.

Output: reproduction/viewer/traces.json  (consumed by index.html)
"""
import json, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SPLIT4 = os.path.join(ROOT, 'reproduction', 'runs', 'autogen_gc', 'split4')
VERDICTS = os.path.join(ROOT, 'reproduction', 'autogen_gc', 'trace_verdicts_split4.json')

TOOL_RESULT_CAP = 6000  # chars; full text remains in the run dir's wire_log.jsonl


def is_selector(row):
    msgs = row.get('messages', [])
    return len(msgs) == 1 and 'Select the SINGLE next member' in json.dumps(msgs)


def extract_turn(last_row):
    """From the final row of an agent's private loop, pull the system role, the ordered
    tool loop (call -> result), and the published message."""
    msgs = last_row.get('messages', [])
    system = ''
    tool_loop = []
    pending = {}
    for m in msgs:
        role = m.get('role')
        if role == 'system' and not system:
            system = m.get('content', '') or ''
        elif role == 'assistant' and m.get('tool_calls'):
            for tc in m['tool_calls']:
                fn = tc.get('function', {})
                args = fn.get('arguments', '')
                try:
                    args = json.dumps(json.loads(args), indent=1)
                except Exception:
                    pass
                pending[tc.get('id')] = {'name': fn.get('name', '?'), 'args': args, 'result': None}
                tool_loop.append(pending[tc.get('id')])
        elif role == 'tool':
            cid = m.get('tool_call_id')
            content = m.get('content', '')
            if isinstance(content, list):
                content = json.dumps(content)
            content = str(content)
            truncated = len(content) > TOOL_RESULT_CAP
            content = content[:TOOL_RESULT_CAP] + ('\n…[truncated]' if truncated else '')
            if cid in pending:
                pending[cid]['result'] = content
            else:
                tool_loop.append({'name': '(result)', 'args': '', 'result': content})
    reply = last_row.get('reply', {})
    published = reply.get('content', '') if isinstance(reply, dict) else str(reply)
    return system, tool_loop, (published or '')


def build_timeline(rows):
    rows = sorted(rows, key=lambda r: r.get('ts', 0))
    # segment into [selector?, agent-rows...] groups
    timeline = []
    i = 0
    pending_selector = None
    n = len(rows)
    while i < n:
        r = rows[i]
        if is_selector(r):
            reply = r.get('reply', {})
            choice = reply.get('content', '') if isinstance(reply, dict) else str(reply)
            pending_selector = {
                'choice': (choice or '').strip(),
                'prompt': r['messages'][0].get('content', ''),
            }
            i += 1
            continue
        # accumulate agent rows until next selector
        seg = []
        while i < n and not is_selector(rows[i]):
            seg.append(rows[i]); i += 1
        last = seg[-1]
        system, tool_loop, published = extract_turn(last)
        # source: infer from system prompt role name
        src = '?'
        for name in ('WebResearcher', 'Analyst', 'Critic', 'Finalizer'):
            if system.strip().startswith(f'You are {name}') or f'You are the {name}' in system[:40] or f'You are {name} ' in system[:40]:
                src = name; break
        if src == '?':
            # fallbacks for Critic/Finalizer phrasing
            if system.startswith('You are the Critic'): src = 'Critic'
            elif system.startswith('You are the Finalizer'): src = 'Finalizer'
        timeline.append({
            'source': src,
            'selector': pending_selector,
            'system': system,
            'tool_loop': tool_loop,
            'published': published,
            'n_internal_calls': len(seg),
        })
        pending_selector = None
    return timeline


def main():
    verdicts = {v['uid8']: v for v in json.load(open(VERDICTS))}
    traces = []
    for d in sorted(glob.glob(os.path.join(SPLIT4, '*'))):
        uid8 = os.path.basename(d)
        runs = sorted(glob.glob(os.path.join(d, 'run_*')))
        if not runs:
            continue
        rundir = runs[-1]
        wl = os.path.join(rundir, 'wire_log.jsonl')
        rj = os.path.join(rundir, 'result.json')
        if not (os.path.exists(wl) and os.path.exists(rj)):
            continue
        result = json.load(open(rj))
        rows = [json.loads(l) for l in open(wl)]
        timeline = build_timeline(rows)
        question = open(os.path.join(rundir, 'prompt.txt'), errors='replace').read().strip()
        v = verdicts.get(uid8, {})
        traces.append({
            'uid8': uid8,
            'uuid': result.get('uuid'),
            'category': result.get('category'),
            'level': result.get('level'),
            'question': question,
            'expected_answer': str(result.get('expected_answer')),
            'final_answer': result.get('final_answer'),
            'exact_match': result.get('exact_match'),
            'seconds': result.get('seconds'),
            'participation': {
                'speaker_turns': result.get('speaker_turns'),
                'tool_calls': result.get('tool_calls'),
                'n_agents_spoke': result.get('n_agents_spoke'),
            },
            'verdict': {
                'outcome': v.get('outcome'),
                'genuine_misalignment': v.get('genuine_misalignment'),
                'mast_codes': v.get('mast_codes'),
                'critic_gate_effect': v.get('critic_gate_effect'),
                'task_description': v.get('task_description'),
                'trace_narrative': v.get('trace_narrative'),
                'open_ended_diagnosis': v.get('open_ended_diagnosis'),
                'mechanism': v.get('mechanism'),
                'key_evidence': v.get('key_evidence'),
            },
            'timeline': timeline,
        })
    out = os.path.join(HERE, 'traces.json')
    json.dump(traces, open(out, 'w'), indent=1)
    size = os.path.getsize(out)
    print(f'wrote {out}  ({len(traces)} traces, {size/1024:.0f} KB)')
    # sanity: turn count vs published speaker turns
    for t in traces:
        ts = t['participation']['speaker_turns'] or {}
        want = sum(ts.values())
        got = len(t['timeline'])
        flag = '' if got == want else '  <-- MISMATCH'
        if flag:
            print(f"  {t['uid8']}: timeline={got} speaker_turns_sum={want}{flag}")
        unk = sum(1 for x in t['timeline'] if x['source'] == '?')
        if unk:
            print(f"  {t['uid8']}: {unk} turns with unknown source")


if __name__ == '__main__':
    main()
