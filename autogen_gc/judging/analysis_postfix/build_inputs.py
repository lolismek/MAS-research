"""Reconstruct per-trace analysis inputs for the split4_openai batch.

The OpenAI-backed runs have NO wire_log.jsonl in the run dir; every model call is
in the global proxy log shared/proxy/raw_calls.jsonl, keyed by `tag`
(agc_split4_openai_<uid8>_run<N>). Each row is ONE model round and carries a
`reasoning` field = the pre-decision reasoning SUMMARY the model emitted before it
acted (called a tool or published).

This rebuilds the SelectorGroupChat timeline the way the topology works:
  selector LLM call (1 message, reply = chosen member)
  -> chosen agent's PRIVATE internal ReAct loop (a run of rows whose messages
     accumulate tool calls + results); the LAST row publishes one message.
For each turn we emit ordered ROUNDS = reason -> act/publish, so the reasoning
summary that preceded each tool call (and the final publish) is attached in order.

One trace per task = its LATEST run (mirrors build_traces.py convention).

Output: analysis_openai/inputs/<uid8>.json  (self-contained; one per subagent)
"""
import json, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # eval-clean repo root
SPLIT4O = os.path.join(ROOT, 'autogen_gc', 'traces', 'split4_openai')
# raw_calls.jsonl (the proxy wire dump) is gitignored/not committed; regenerating
# inputs/ requires re-running the batch with the proxy logging on. See shared/proxy/README.md.
RAW = os.path.join(ROOT, 'shared', 'proxy', 'raw_calls.jsonl')
OUTDIR = os.path.join(HERE, 'inputs')

TOOL_RESULT_CAP = 6000  # chars per tool result (full text stays in raw_calls.jsonl)


def is_selector(row):
    # The marker phrase appears ONLY in the selector's system prompt, so detect on
    # it alone — robust to selector calls that carry >1 message or whose reply is a
    # malformed non-member string (itself a routing-failure signal worth surfacing).
    return 'Select the SINGLE next member' in json.dumps(row.get('messages', []))


def infer_source(system):
    s = (system or '').strip()
    for name in ('WebResearcher', 'Analyst', 'Critic', 'Finalizer'):
        if s.startswith(f'You are {name}') or s.startswith(f'You are the {name}'):
            return name
    return '?'


def cap(content):
    if isinstance(content, list):
        content = json.dumps(content)
    content = str(content)
    if len(content) > TOOL_RESULT_CAP:
        content = content[:TOOL_RESULT_CAP] + '\n…[truncated]'
    return content


def build_turn(seg):
    """seg = ordered list of raw rows for one agent turn (its private ReAct loop)."""
    seg = sorted(seg, key=lambda r: r['ts'])
    system = ''
    for m in seg[0].get('messages', []):
        if m.get('role') == 'system':
            system = m.get('content', '') or ''
            break
    # global map of tool results across the whole segment (results land in later rows)
    results = {}
    for row in seg:
        for m in row.get('messages', []):
            if m.get('role') == 'tool':
                results[m.get('tool_call_id')] = cap(m.get('content', ''))
    rounds = []
    for row in seg:
        reasoning = (row.get('reasoning') or '').strip()
        reply = row.get('reply', {})
        tcs = reply.get('tool_calls') if isinstance(reply, dict) else None
        if tcs:
            tools = []
            for tc in tcs:
                fn = tc.get('function', {})
                args = fn.get('arguments', '')
                try:
                    args = json.dumps(json.loads(args), indent=1)
                except Exception:
                    pass
                tools.append({'name': fn.get('name', '?'), 'args': args,
                              'result': results.get(tc.get('id'))})
            rounds.append({'reasoning': reasoning, 'tools': tools, 'publish': None})
        else:
            content = reply.get('content', '') if isinstance(reply, dict) else str(reply)
            rounds.append({'reasoning': reasoning, 'tools': [], 'publish': content or ''})
    published = ''
    last_reply = seg[-1].get('reply', {})
    if isinstance(last_reply, dict):
        published = last_reply.get('content', '') or ''
    return system, rounds, published


def build_timeline(rows):
    rows = sorted(rows, key=lambda r: r['ts'])
    timeline, i, n = [], 0, len(rows)
    pending_sel = None
    while i < n:
        r = rows[i]
        if is_selector(r):
            reply = r.get('reply', {})
            choice = reply.get('content', '') if isinstance(reply, dict) else str(reply)
            pending_sel = {'choice': (choice or '').strip(),
                           'reasoning': (r.get('reasoning') or '').strip(),
                           'prompt': r['messages'][0].get('content', '')}
            i += 1
            continue
        seg = []
        while i < n and not is_selector(rows[i]):
            seg.append(rows[i]); i += 1
        system, rounds, published = build_turn(seg)
        src = infer_source(system)
        timeline.append({'source': src, 'selector': pending_sel, 'system': system,
                         'rounds': rounds, 'published': published,
                         'n_internal_calls': len(seg)})
        pending_sel = None
    return timeline


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    raw = [json.loads(l) for l in open(RAW)]
    by_tag = {}
    for r in raw:
        by_tag.setdefault(r.get('tag', ''), []).append(r)

    summary = []
    for d in sorted(glob.glob(os.path.join(SPLIT4O, '*'))):
        uid8 = os.path.basename(d)
        runs = sorted(glob.glob(os.path.join(d, 'run_*')),
                      key=lambda p: int(p.rsplit('_', 1)[1]))
        if not runs:
            continue
        rundir = runs[-1]
        runN = int(rundir.rsplit('_', 1)[1])
        rj = os.path.join(rundir, 'result.json')
        if not os.path.exists(rj):
            continue
        result = json.load(open(rj))
        tag = f'agc_split4_openai_{uid8}_run{runN}'
        rows = by_tag.get(tag, [])
        timeline = build_timeline(rows) if rows else []
        # Some runs hung with zero logged OpenAI calls (infra failure, not a MAS
        # dynamic). Flag so the subagent treats it as no-data rather than guessing.
        no_data = len(rows) == 0
        question = open(os.path.join(rundir, 'prompt.txt'), errors='replace').read().strip()
        n_reason = sum(1 for t in timeline for rd in t['rounds'] if rd['reasoning']) \
            + sum(1 for t in timeline if t['selector'] and t['selector']['reasoning'])
        n_rounds = sum(len(t['rounds']) for t in timeline)
        unk = sum(1 for t in timeline if t['source'] == '?')
        bundle = {
            'uid8': uid8, 'uuid': result.get('uuid'),
            'category': result.get('category'), 'level': result.get('level'),
            'run': runN, 'tag': tag, 'no_data': no_data,
            'console_log_excerpt': open(os.path.join(rundir, 'console_log.txt'),
                                        errors='replace').read()[:4000] if no_data else None,
            'question': question,
            'expected_answer': str(result.get('expected_answer')),
            'final_answer': result.get('final_answer'),
            'exact_match': result.get('exact_match'),
            'seconds': result.get('seconds'),
            'rc': result.get('rc'),
            'participation': {
                'speaker_turns': result.get('speaker_turns'),
                'tool_calls': result.get('tool_calls'),
                'n_agents_spoke': result.get('n_agents_spoke'),
            },
            'timeline': timeline,
        }
        json.dump(bundle, open(os.path.join(OUTDIR, f'{uid8}.json'), 'w'), indent=1)
        summary.append((uid8, runN, len(rows), len(timeline), n_rounds, n_reason, unk,
                        result.get('exact_match'), result.get('final_answer')))

    print(f'{"uid8":10} {"run":>3} {"rows":>4} {"turns":>5} {"rounds":>6} '
          f'{"reason":>6} {"unk":>3} {"match":>5}  final')
    for s in summary:
        uid8, runN, nrows, nturns, nrounds, nreason, unk, match, final = s
        flag = '  <-- UNKNOWN SRC' if unk else ('  <-- NO ROWS' if nrows == 0 else '')
        print(f'{uid8:10} {runN:>3} {nrows:>4} {nturns:>5} {nrounds:>6} '
              f'{nreason:>6} {unk:>3} {str(match):>5}  {str(final)[:30]}{flag}')
    print(f'\n{len(summary)} traces written to {OUTDIR}')


if __name__ == '__main__':
    main()
