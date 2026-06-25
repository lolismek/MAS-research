"""Run selected GAIA tasks through the AutoGen SelectorGroupChat MAS.

Second MAS baseline for the inter-agent-misalignment study (contrast to
Magentic-One's star). Each task runs a 3-peer SelectorGroupChat
(WebResearcher / Analyst / Verifier); each agent is an
AssistantAgent(max_tool_iterations=K) that does a deep PRIVATE tool loop and
publishes one message to the shared chat (see scenario_template.py).

This mirrors reproduction/magentic/run_task.py and reuses the same proxy
(chat.completions -> Perplexity /responses; model alias "gpt-4o" ->
gpt-5.4-mini), the same tagged-endpoint attribution, and the SAME answer
parsing/normalization + result.json schema. It deliberately does NOT use the
browser or the _debing patch — web access is function tools (tools.py).

Env: conda env autogen_gc (autogen-agentchat/core/ext >= 0.6.2).

Topology variant is selected with --variant {selector3 (default), split4}; results
are namespaced by variant under runs/autogen_gc/<variant>/<uid8>/run_*.

Usage (from the eval-clean repo root):
  conda run -n autogen_gc python autogen_gc/harness/run_task.py 0383a3ee [..]
  conda run -n autogen_gc python autogen_gc/harness/run_task.py --all
  conda run -n autogen_gc python autogen_gc/harness/run_task.py --all --parallel 4
  conda run -n autogen_gc python autogen_gc/harness/run_task.py --all --variant split4 --parallel 4
  conda run -n autogen_gc python autogen_gc/harness/run_task.py --all --variant split4 --shared-memory --parallel 4

Add --shared-memory to enable the shared "thinking memory" board (board runs are
namespaced traces/split4_board/...). Add --no-selector-board alongside it for the
agents-only ablation (board on for agents, selector left stock).
"""
import functools, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)            # the autogen_gc/ MAS dir
REPO_ROOT = os.path.dirname(ROOT)       # eval-clean repo root
TASKS = json.load(open(os.path.join(ROOT, 'tasks', 'autogen_gc_tasks.json')))
RUNS = os.path.join(ROOT, 'traces')     # re-runs namespace under traces/<variant>[_<backend>]/
# For reused GAIA tasks, prompt.txt is read from the external mast_repo clone
# (gitignored); task['trace_dir'] is relative to it. Defaults to repo root.
REF_ROOT = os.environ.get('MAST_REPO_ROOT', REPO_ROOT)
PROXY = os.environ.get('PROXY_URL', 'http://127.0.0.1:8744/v1')
TIMEOUT = int(os.environ.get('TASK_TIMEOUT', '1800'))

# Topology variants share the ENTIRE harness (tools, proxy, scoring, task set) and
# differ only in the scenario file (team construction), so the comparison isolates
# topology. Results are namespaced by variant: runs/autogen_gc/<variant>/<uid8>/.
VARIANTS = {
    'split4': os.path.join(HERE, 'scenario_split.py'),        # 4-agent (WebResearcher/Analyst/Critic/Finalizer)
}


def make_config(tag, backend='pplx'):
    # /t/<tag>/v1 routes through the proxy's tagged endpoint so every
    # calls.jsonl / raw_calls.jsonl entry is attributable to this run.
    # /o/<tag>/v1 routes to OpenAI direct (reasoning summaries captured); /t to
    # Perplexity (no reasoning). Same chat.completions wire on the client side.
    base, v1 = PROXY.rsplit('/', 1)
    seg = {'openai': 'o', 'tinker': 'm'}.get(backend, 't')   # 'm' -> Tinker chat passthrough
    return {'model': 'gpt-4o', 'base_url': f'{base}/{seg}/{tag}/{v1}', 'api_key': 'dummy'}


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[,$%]', '', (s or '').strip().lower()))


def participation(text):
    """Parse the AutoGen Console log into per-agent participation stats so we can
    tell a genuine multi-agent run from one that collapsed to a single speaker.

    Console headers look like ``---------- <EventType> (<name>) ----------``:
    ``TextMessage`` = one PUBLISHED turn; ``ToolCallRequestEvent`` = one PRIVATE
    tool call inside that agent's hidden session.
    """
    hdr = re.findall(r'^-{3,}\s*(\w+)\s*\((\w+)\)\s*-{3,}', text, re.M)
    speaker_turns, tool_calls = {}, {}
    for ev, name in hdr:
        if ev == 'TextMessage' and name != 'user':
            speaker_turns[name] = speaker_turns.get(name, 0) + 1
        elif ev == 'ToolCallRequestEvent':
            tool_calls[name] = tool_calls.get(name, 0) + 1
    n_spoke = len(speaker_turns)
    return dict(speaker_turns=speaker_turns, tool_calls=tool_calls,
                n_agents_spoke=n_spoke, single_agent=n_spoke <= 1)


def run_one(task, variant='selector3', backend='pplx', shared_memory=False, selector_board=True):
    uid8 = task['uuid'][:8]
    # Board runs get their own namespace so A/B arms never mix; the agents-only ablation
    # (selector left stock) is namespaced again. OpenAI-backed runs are suffixed
    # (…_openai) so they never mix with the Perplexity runs of the same arm.
    label = variant
    if shared_memory:
        label += '_board' if selector_board else '_board_agentsonly'
    runs_v = os.path.join(RUNS, label if backend == 'pplx' else f'{label}_{backend}')
    n = 1
    while os.path.exists(os.path.join(runs_v, uid8, f'run_{n}')):
        n += 1
    rundir = os.path.join(runs_v, uid8, f'run_{n}')
    os.makedirs(rundir)

    # prompt.txt: prefer the original extracted prompt (exact comparability for the
    # reused tasks), else fall back to the task's question field.
    src_prompt = os.path.join(REF_ROOT, task.get('trace_dir', ''), 'prompt.txt')
    if task.get('trace_dir') and os.path.exists(src_prompt):
        shutil.copy(src_prompt, os.path.join(rundir, 'prompt.txt'))
    else:
        with open(os.path.join(rundir, 'prompt.txt'), 'w') as f:
            f.write(task['question'])
    with open(os.path.join(rundir, 'expected_answer.txt'), 'w') as f:
        f.write(str(task['expected_answer']))
    shutil.copy(VARIANTS[variant], os.path.join(rundir, 'scenario.py'))
    btag = '' if backend == 'pplx' else f'{backend}_'
    with open(os.path.join(rundir, 'config.yaml'), 'w') as f:
        # JSON is valid YAML; tag encodes backend so raw_calls.jsonl stays attributable.
        json.dump(make_config(f'agc_{label}_{btag}{uid8}_run{n}', backend), f)

    print(f'[{variant}/{uid8}] run_{n} starting (timeout {TIMEOUT}s)', flush=True)
    t0 = time.time()
    # Put autogen_gc/harness on PYTHONPATH so the copied scenario.py can
    # `import tools` (web_search / fetch_url / run_python).
    env = dict(os.environ)
    env['PYTHONPATH'] = HERE + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    if shared_memory:
        env['SHARED_MEMORY'] = '1'
        env['SELECTOR_BOARD'] = '1' if selector_board else '0'
    with open(os.path.join(rundir, 'console_log.txt'), 'w') as log:
        try:
            rc = subprocess.run([sys.executable, 'scenario.py'], cwd=rundir,
                                env=env, stdout=log, stderr=subprocess.STDOUT,
                                timeout=TIMEOUT).returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
    dur = time.time() - t0

    tail = open(os.path.join(rundir, 'console_log.txt'), errors='replace').read()
    m = re.findall(r'FINAL ANSWER:\s*(.+)', tail)
    final = m[-1].strip() if m else None
    expected = task['expected_answer']
    part = participation(tail)
    board_stats = {}
    if shared_memory:
        btf = os.path.join(rundir, 'board_trace.jsonl')
        evs = [json.loads(l) for l in open(btf) if l.strip()] if os.path.exists(btf) else []
        board_stats = dict(shared_memory=True, selector_board=selector_board,
                           board_event_count=len(evs),
                           board_note_count=sum(1 for e in evs if e.get('op') == 'add'),
                           board_revise_count=sum(1 for e in evs if e.get('op') == 'revise'),
                           board_authors=sorted({e['agent'] for e in evs}))
    result = dict(uuid=task['uuid'], variant=variant, backend=backend, run=n, rc=rc, seconds=round(dur, 1),
                  level=task.get('level'), category=task.get('category'),
                  final_answer=final, expected_answer=expected,
                  exact_match=final is not None and norm(final) == norm(expected),
                  original_success=task.get('success'),
                  **part, **board_stats)
    with open(os.path.join(rundir, 'result.json'), 'w') as f:
        json.dump(result, f, indent=1)
    print(f'[{variant}/{uid8}] rc={rc} {dur:.0f}s final={final!r} expected={expected!r} '
          f'match={result["exact_match"]} spoke={part["n_agents_spoke"]} '
          f'turns={part["speaker_turns"]} tools={part["tool_calls"]}', flush=True)
    return result


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    par = 1
    if '--parallel' in args:
        i = args.index('--parallel')
        par = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    variant = 'split4'
    if '--variant' in args:
        i = args.index('--variant')
        variant = args[i + 1]
        args = args[:i] + args[i + 2:]
    if variant not in VARIANTS:
        sys.exit(f'unknown --variant {variant!r}; choose from {list(VARIANTS)}')
    backend = 'pplx'
    if '--backend' in args:
        i = args.index('--backend')
        backend = args[i + 1]
        args = args[:i] + args[i + 2:]
    if backend not in ('pplx', 'openai', 'tinker'):
        sys.exit(f'unknown --backend {backend!r}; choose from pplx, openai, tinker')
    shared_memory = '--shared-memory' in args
    if shared_memory:
        args = [a for a in args if a != '--shared-memory']
    selector_board = '--no-selector-board' not in args
    if not selector_board:
        args = [a for a in args if a != '--no-selector-board']
    sel = TASKS if args == ['--all'] else [
        t for t in TASKS if any(t['uuid'].startswith(a) for a in args)]
    if args != ['--all'] and len(sel) != len(args):
        sys.exit(f'unmatched uuid prefixes; matched {[t["uuid"][:8] for t in sel]}')
    run = functools.partial(run_one, variant=variant, backend=backend,
                            shared_memory=shared_memory, selector_board=selector_board)
    if par == 1:
        results = [run(t) for t in sel]
    else:
        from concurrent.futures import ThreadPoolExecutor  # run_one is subprocess-bound
        with ThreadPoolExecutor(max_workers=par) as ex:
            results = list(ex.map(run, sel))
    print(json.dumps(results, indent=1))


if __name__ == '__main__':
    main()
