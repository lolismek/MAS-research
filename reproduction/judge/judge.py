"""Two-stage MAST judge over original (GPT-4o) and new (gpt-5.4-mini) traces.

Judge model: openai/gpt-5.5 via Perplexity Responses API, temperature 0
(strongest available; also a different model family generation than the MAS
under test, avoiding self-judging bias). Direct API calls — NOT through the
reproduction proxy, which aliases every model to the MAS model.

Per trace -> reproduction/judged/<era>/<system>/<id>.json:
  stage_a: taxonomy-blind close reading (narrative + open-ended findings list)
  stage_b: 14 MAST binary modes, each with mandatory verbatim evidence
  usage/cost for both calls. Resume-safe: existing outputs are skipped.

Both eras are judged from the SAME fidelity (console/dialogue logs), so
old-vs-new mode statistics are comparable. Raw wire dumps exist only for new
runs and are deliberately NOT shown to the judge.

Usage:
  conda run -n base python reproduction/judge/judge.py --smoke <trace-file>
  conda run -n base python reproduction/judge/judge.py --original --new [--parallel 4]
"""
import argparse, glob, json, os, re, sys, time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for line in open(os.path.join(ROOT, '.env')):
    if '=' in line:
        k, v = line.strip().split('=', 1)
        os.environ.setdefault(k, v)

sys.path.insert(0, HERE)
from prompts import build_stage_a, build_stage_b, MAST_MODES

JUDGE_MODEL = os.environ.get('JUDGE_MODEL', 'openai/gpt-5.5')
BASE = 'https://api.perplexity.ai/v1'
KEY = os.environ['PERPLEXITY_API_KEY']
OUT = os.path.join(ROOT, 'reproduction', 'judged')
MAX_TRACE_CHARS = 400_000  # head+tail truncation beyond this
DEFINITIONS = open(os.path.join(ROOT, 'mast_repo', 'taxonomy_definitions_examples',
                                'definitions.txt'), errors='replace').read()
EXAMPLES = open(os.path.join(ROOT, 'mast_repo', 'taxonomy_definitions_examples',
                             'examples.txt'), errors='replace').read()


def call_judge(prompt):
    body = dict(model=JUDGE_MODEL, store=False, temperature=0,
                text=dict(format=dict(type='json_object')),
                input=[dict(role='user', content=prompt)])
    for attempt in range(4):
        r = requests.post(f'{BASE}/responses', json=body, timeout=900,
                          headers={'Authorization': f'Bearer {KEY}'})
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(15 * (attempt + 1))
            continue
        r.raise_for_status()
        j = r.json()
        text = ''.join(c.get('text', '') for o in j.get('output', [])
                       if o.get('type') == 'message'
                       for c in o.get('content', []))
        u = j.get('usage') or {}
        usage = dict(input_tokens=u.get('input_tokens'),
                     output_tokens=u.get('output_tokens'),
                     cost=(u.get('cost') or {}).get('total_cost'))
        try:
            return json.loads(text), usage
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', text, re.S)  # salvage fenced/wrapped JSON
            if m:
                return json.loads(m.group(0)), usage
            if attempt == 3:
                raise
    raise RuntimeError('judge call failed after retries')


def truncate(t):
    if len(t) <= MAX_TRACE_CHARS:
        return t
    h = MAX_TRACE_CHARS // 2
    return t[:h] + '\n...[MIDDLE OF TRACE TRUNCATED]...\n' + t[-h:]


def judge_trace(trace_text, meta):
    trace_text = truncate(trace_text)
    a, ua = call_judge(build_stage_a(trace_text))
    b, ub = call_judge(build_stage_b(
        trace_text, DEFINITIONS, EXAMPLES,
        json.dumps(a.get('findings', []), indent=1)))
    # normalize stage_b modes: every mode key present, evidence required
    modes = {}
    for m in MAST_MODES:
        e = (b.get('modes') or {}).get(m) or {}
        present = bool(e.get('present')) and bool(e.get('evidence'))
        modes[m] = dict(present=present, evidence=e.get('evidence'),
                        note=e.get('note'))
        if e.get('present') and not e.get('evidence'):
            modes[m]['note'] = ((e.get('note') or '')
                                + ' [flag dropped: no evidence quote]').strip()
    return dict(meta=meta, judge_model=JUDGE_MODEL,
                stage_a=a, stage_b=dict(task_success=b.get('task_success'),
                                        summary=b.get('summary'), modes=modes),
                usage=dict(stage_a=ua, stage_b=ub))


# ---------------------------------------------------------------- corpus ----
def corpus():
    """Yield (era, system, id, trace_path, meta)."""
    mag = json.load(open(os.path.join(ROOT, 'task_selection',
                                      'magentic_gaia_tasks.json')))
    for t in mag:
        u = t['uuid'][:8]
        yield ('original', 'magentic', u,
               os.path.join(ROOT, t['trace_dir'], 'console_log.txt'),
               dict(uuid=t['uuid'], level=t['level'],
                    original_success=t['success'],
                    cat2_screened=t.get('cat2_likelihood_screened')))
        for rdir in sorted(glob.glob(os.path.join(
                ROOT, 'reproduction', 'runs', 'magentic', u, 'run_*'))):
            res = os.path.join(rdir, 'result.json')
            if os.path.exists(res):
                r = json.load(open(res))
                yield ('new', 'magentic', f'{u}_{os.path.basename(rdir)}',
                       os.path.join(rdir, 'console_log.txt'),
                       dict(uuid=t['uuid'], level=t['level'],
                            new_exact_match=r['exact_match'],
                            original_success=t['success'],
                            cat2_screened=t.get('cat2_likelihood_screened')))
    cd = json.load(open(os.path.join(ROOT, 'task_selection',
                                     'chatdev_tasks.json')))
    ALIASES = {'TicTacToe (with display)': 'TicTacToe',
               'The Crossword': 'TheCrossword',
               'Connections': 'ConnectionsNYT', 'Strands': 'StrandsNYT'}
    for t in cd:
        name = ALIASES.get(t['task'], t['task'])
        slug = name.replace(' ', '')
        orig = os.path.join(ROOT, 'task_selection', 'original_traces',
                            'chatdev', name.replace(' ', '_') + '.log')
        yield ('original', 'chatdev', slug, orig,
               dict(task=t['task'], original_solved=t['solved'],
                    human_cat2=t['cat2'],
                    cat2_screened=t.get('cat2_likelihood_screened')))
        for rdir in sorted(glob.glob(os.path.join(
                ROOT, 'reproduction', 'runs', 'chatdev', slug, 'run_*'))):
            logs = glob.glob(os.path.join(rdir, 'warehouse', '*.log'))
            if logs:
                yield ('new', 'chatdev', f'{slug}_{os.path.basename(rdir)}',
                       logs[0],
                       dict(task=t['task'], original_solved=t['solved'],
                            human_cat2=t['cat2'],
                            cat2_screened=t.get('cat2_likelihood_screened')))

    # MacNet (no 'original' era: these systems have no MAST-era traces).
    # macnet-chain / macnet-mesh reuse the chatdev tasks; macnet-srdd has its
    # own task file. Trace = MacNetLog transcript archived as trace.log.
    def macnet_runs(system, tasks, base_meta):
        for t in tasks:
            name = ALIASES.get(t['task'], t['task'])
            slug = name.replace(' ', '').replace('/', '_')
            for rdir in sorted(glob.glob(os.path.join(
                    ROOT, 'reproduction', 'runs', system, slug, 'run_*'))):
                trace = os.path.join(rdir, 'trace.log')
                if not os.path.exists(trace):
                    continue
                res = {}
                if os.path.exists(os.path.join(rdir, 'result.json')):
                    res = json.load(open(os.path.join(rdir, 'result.json')))
                yield ('new', system, f'{slug}_{os.path.basename(rdir)}',
                       trace, dict(task=t['task'],
                                   topology=res.get('topology'),
                                   n_nodes=res.get('n_nodes'),
                                   **base_meta(t)))

    for cfg in ('chain', 'mlp', 'net'):
        yield from macnet_runs(
            f'macnet-{cfg}', cd,
            lambda t: dict(original_solved=t['solved'], human_cat2=t['cat2'],
                           cat2_screened=t.get('cat2_likelihood_screened')))
    srdd_file = os.path.join(ROOT, 'task_selection', 'macnet_srdd_tasks.json')
    if os.path.exists(srdd_file):
        yield from macnet_runs(
            'macnet-srdd', json.load(open(srdd_file)),
            lambda t: dict(category=t.get('category'), original_solved=None,
                           cat2_screened=None))

    # DyLAN: trace = transcript.txt rebuilt from DyLAN's own completion log;
    # ground-truth outcome (final_correct) comes from result.json.
    # dylan = 7-role MMLU arm; dylan-math = 7-specialist MATH level-5 arm
    # (free-form answers, added after MMLU's round-1 early stops produced
    # structurally thin traces).
    for system, taskfile, runsdir in (
            ('dylan', 'dylan_tasks.json', 'dylan'),
            ('dylan-math', 'dylan_math_tasks.json', 'dylan-math')):
        dylan_file = os.path.join(ROOT, 'task_selection', taskfile)
        if not os.path.exists(dylan_file):
            continue
        for t in json.load(open(dylan_file)):
            for rdir in sorted(glob.glob(os.path.join(
                    ROOT, 'reproduction', 'runs', runsdir, t['id'], 'run_*'))):
                trace = os.path.join(rdir, 'transcript.txt')
                if not os.path.exists(trace):
                    continue
                res = {}
                if os.path.exists(os.path.join(rdir, 'result.json')):
                    res = json.load(open(os.path.join(rdir, 'result.json')))
                yield ('new', system, f"{t['id']}_{os.path.basename(rdir)}",
                       trace, dict(subject=t['subject'],
                                   baseline_solved=t['solved'],
                                   new_exact_match=res.get('final_correct'),
                                   cat2_screened=None))


def run_one(item):
    era, system, tid, path, meta = item
    out = os.path.join(OUT, era, system, tid + '.json')
    if os.path.exists(out):
        print(f'skip (exists): {era}/{system}/{tid}', flush=True)
        return
    if not os.path.exists(path):
        print(f'MISSING TRACE: {era}/{system}/{tid}: {path}', flush=True)
        return
    os.makedirs(os.path.dirname(out), exist_ok=True)
    t0 = time.time()
    try:
        res = judge_trace(open(path, errors='replace').read(),
                          dict(era=era, system=system, id=tid, trace=path,
                               **meta))
    except Exception as e:
        print(f'ERROR {era}/{system}/{tid}: {e}', flush=True)
        return
    json.dump(res, open(out, 'w'), indent=1)
    flagged = [m for m, v in res['stage_b']['modes'].items() if v['present']]
    cost = sum(res['usage'][s]['cost'] or 0 for s in ('stage_a', 'stage_b'))
    print(f'{era}/{system}/{tid}: modes={",".join(flagged) or "-"} '
          f'findings={len(res["stage_a"].get("findings", []))} '
          f'${cost:.2f} {time.time()-t0:.0f}s', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--smoke', help='judge one trace file and print result')
    ap.add_argument('--original', action='store_true')
    ap.add_argument('--new', action='store_true')
    ap.add_argument('--only', help='comma-separated id prefixes to include')
    ap.add_argument('--parallel', type=int, default=1)
    args = ap.parse_args()

    if args.smoke:
        res = judge_trace(open(args.smoke, errors='replace').read(),
                          dict(era='smoke', trace=args.smoke))
        print(json.dumps(res, indent=1))
        return

    items = [c for c in corpus()
             if (c[0] == 'original' and args.original)
             or (c[0] == 'new' and args.new)]
    if args.only:
        pres = args.only.split(',')
        items = [c for c in items if any(c[2].startswith(p) for p in pres)]
    print(f'{len(items)} traces to judge with {JUDGE_MODEL}')
    if args.parallel > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=args.parallel) as ex:
            list(ex.map(run_one, items))
    else:
        for it in items:
            run_one(it)


if __name__ == '__main__':
    main()
