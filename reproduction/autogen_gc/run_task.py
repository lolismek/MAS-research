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

Usage:
  conda run -n autogen_gc python reproduction/autogen_gc/run_task.py 0383a3ee [..]
  conda run -n autogen_gc python reproduction/autogen_gc/run_task.py --all
  conda run -n autogen_gc python reproduction/autogen_gc/run_task.py --all --parallel 4
"""
import json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TASKS = json.load(open(os.path.join(ROOT, 'task_selection', 'autogen_gc_tasks.json')))
RUNS = os.path.join(ROOT, 'reproduction', 'runs', 'autogen_gc')
SCENARIO = os.path.join(HERE, 'scenario_template.py')
PROXY = os.environ.get('PROXY_URL', 'http://127.0.0.1:8744/v1')
TIMEOUT = int(os.environ.get('TASK_TIMEOUT', '1800'))


def make_config(tag):
    # /t/<tag>/v1 routes through the proxy's tagged endpoint so every
    # calls.jsonl / raw_calls.jsonl entry is attributable to this run.
    base, v1 = PROXY.rsplit('/', 1)
    return {'model': 'gpt-4o', 'base_url': f'{base}/t/{tag}/{v1}', 'api_key': 'dummy'}


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[,$%]', '', (s or '').strip().lower()))


def run_one(task):
    uid8 = task['uuid'][:8]
    n = 1
    while os.path.exists(os.path.join(RUNS, uid8, f'run_{n}')):
        n += 1
    rundir = os.path.join(RUNS, uid8, f'run_{n}')
    os.makedirs(rundir)

    # prompt.txt: prefer the original extracted prompt (exact comparability for the
    # reused tasks), else fall back to the task's question field.
    src_prompt = os.path.join(ROOT, task.get('trace_dir', ''), 'prompt.txt')
    if task.get('trace_dir') and os.path.exists(src_prompt):
        shutil.copy(src_prompt, os.path.join(rundir, 'prompt.txt'))
    else:
        with open(os.path.join(rundir, 'prompt.txt'), 'w') as f:
            f.write(task['question'])
    with open(os.path.join(rundir, 'expected_answer.txt'), 'w') as f:
        f.write(str(task['expected_answer']))
    shutil.copy(SCENARIO, os.path.join(rundir, 'scenario.py'))
    with open(os.path.join(rundir, 'config.yaml'), 'w') as f:
        json.dump(make_config(f'agc_{uid8}_run{n}'), f)  # JSON is valid YAML

    print(f'[{uid8}] run_{n} starting (timeout {TIMEOUT}s)', flush=True)
    t0 = time.time()
    # Put reproduction/autogen_gc on PYTHONPATH so the copied scenario.py can
    # `import tools` (web_search / fetch_url / run_python).
    env = dict(os.environ)
    env['PYTHONPATH'] = HERE + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
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
    result = dict(uuid=task['uuid'], run=n, rc=rc, seconds=round(dur, 1),
                  level=task.get('level'),
                  final_answer=final, expected_answer=expected,
                  exact_match=final is not None and norm(final) == norm(expected),
                  original_success=task.get('success'))
    with open(os.path.join(rundir, 'result.json'), 'w') as f:
        json.dump(result, f, indent=1)
    print(f'[{uid8}] rc={rc} {dur:.0f}s final={final!r} expected={expected!r} '
          f'match={result["exact_match"]}', flush=True)
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
    sel = TASKS if args == ['--all'] else [
        t for t in TASKS if any(t['uuid'].startswith(a) for a in args)]
    if args != ['--all'] and len(sel) != len(args):
        sys.exit(f'unmatched uuid prefixes; matched {[t["uuid"][:8] for t in sel]}')
    if par == 1:
        results = [run_one(t) for t in sel]
    else:
        from concurrent.futures import ThreadPoolExecutor  # run_one is subprocess-bound
        with ThreadPoolExecutor(max_workers=par) as ex:
            results = list(ex.map(run_one, sel))
    print(json.dumps(results, indent=1))


if __name__ == '__main__':
    main()
