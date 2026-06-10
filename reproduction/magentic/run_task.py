"""Run selected GAIA tasks through the NATIVE Magentic-One harness.

Re-executes the MAST authors' own agbench run package: each original trace dir
(mast_repo/traces/MagenticOne_GAIA/...) contains the exact scenario.py that
produced the original GPT-4o trace (verified byte-identical to the agbench
GAIA MagenticOne template at microsoft/autogen@af5dcc7, 2025-02-07, modulo the
per-task __FILE_NAME__ substitution). We copy that scenario.py VERBATIM into a
fresh run dir and only swap config.yaml so the model client points at the
local chat.completions->Perplexity proxy (model alias "gpt-4o" ->
openai/gpt-5.4-mini; keeps AutoGen's gpt-4o model_info: vision+tools).

Env: conda env magentic_v04 (autogen-core/agentchat/ext==0.4.8 — the release
window between the template commit and the MAST paper, 2025-02-07..03-13 —
plus playwright chromium).

Usage:
  conda run -n magentic_v04 python reproduction/magentic/run_task.py 0383a3ee [27d5d136 ...]
  conda run -n magentic_v04 python reproduction/magentic/run_task.py --all
"""
import json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TASKS = json.load(open(os.path.join(ROOT, 'task_selection', 'magentic_gaia_tasks.json')))
RUNS = os.path.join(ROOT, 'reproduction', 'runs', 'magentic')
PROXY = os.environ.get('PROXY_URL', 'http://127.0.0.1:8744/v1')
TIMEOUT = int(os.environ.get('TASK_TIMEOUT', '7200'))  # matches original run.sh

def make_config(tag):
    # /t/<tag>/v1 routes through the proxy's tagged endpoint so every
    # calls.jsonl / raw_calls.jsonl entry is attributable to this run,
    # even when tasks execute in parallel.
    base, v1 = PROXY.rsplit('/', 1)
    return f"""\
model_config: &client
  provider: autogen_ext.models.openai.OpenAIChatCompletionClient
  config:
    model: gpt-4o
    base_url: {base}/t/{tag}/{v1}
    api_key: dummy

orchestrator_client: *client
coder_client: *client
web_surfer_client: *client
file_surfer_client: *client
"""


def run_one(task):
    uid8 = task['uuid'][:8]
    src = os.path.join(ROOT, task['trace_dir'])
    n = 1
    while os.path.exists(os.path.join(RUNS, uid8, f'run_{n}')):
        n += 1
    rundir = os.path.join(RUNS, uid8, f'run_{n}')
    os.makedirs(rundir)
    os.makedirs(os.path.join(rundir, 'logs'))

    for f in ['prompt.txt', 'expected_answer.txt', 'scenario.py'] + task['attachments']:
        shutil.copy(os.path.join(src, f), rundir)
    with open(os.path.join(rundir, 'config.yaml'), 'w') as f:
        f.write(make_config(f'mag_{uid8}_run{n}'))

    print(f'[{uid8}] run_{n} starting (timeout {TIMEOUT}s)', flush=True)
    t0 = time.time()
    with open(os.path.join(rundir, 'console_log.txt'), 'w') as log:
        try:
            rc = subprocess.run([sys.executable, 'scenario.py'], cwd=rundir,
                                stdout=log, stderr=subprocess.STDOUT,
                                timeout=TIMEOUT).returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
    dur = time.time() - t0

    tail = open(os.path.join(rundir, 'console_log.txt'), errors='replace').read()
    import re
    m = re.findall(r'FINAL ANSWER:\s*(.+)', tail)
    final = m[-1].strip() if m else None
    expected = task['expected_answer']

    def norm(s):
        return re.sub(r'\s+', ' ', re.sub(r'[,$%]', '', (s or '').strip().lower()))

    result = dict(uuid=task['uuid'], run=n, rc=rc, seconds=round(dur, 1),
                  final_answer=final, expected_answer=expected,
                  exact_match=final is not None and norm(final) == norm(expected),
                  original_success=task['success'])
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
    if len(sel) != (len(TASKS) if args == ['--all'] else len(args)):
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
