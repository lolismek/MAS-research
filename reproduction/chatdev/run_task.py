"""Run selected ProgramDev tasks through NATIVE ChatDev v1.1.6.

Invokes chatdev_repo's own run.py per task (Default ChatChain, --model GPT_4O
aliased to gpt-5.4-mini by the proxy). Project names are the MAD project_names
from the original traces, so prompts see the same name the GPT-4o runs saw.
Each run gets a tagged proxy route (/t/cd_<name>_runN/v1) so calls.jsonl and
raw_calls.jsonl stay attributable under parallel execution. The produced
WareHouse directory (code + full dialogue log) is archived into the run dir.

Usage:
  conda run -n chatdev_v1 python reproduction/chatdev/run_task.py Gomoku Sudoku
  conda run -n chatdev_v1 python reproduction/chatdev/run_task.py --all [--parallel 4]
"""
import glob, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.join(ROOT, 'reproduction', 'chatdev_repo')
RUNS = os.path.join(ROOT, 'reproduction', 'runs', 'chatdev')
TASKS = json.load(open(os.path.join(ROOT, 'task_selection', 'chatdev_tasks.json')))
PROXY = os.environ.get('PROXY_URL', 'http://127.0.0.1:8744/v1')
TIMEOUT = int(os.environ.get('TASK_TIMEOUT', '3600'))

ALIASES = {  # selection CSV name -> MAD project_name (same map as build_selection.py)
    'TicTacToe (with display)': 'TicTacToe', 'The Crossword': 'TheCrossword',
    'Connections': 'ConnectionsNYT', 'Strands': 'StrandsNYT',
}


def run_one(task):
    name = ALIASES.get(task['task'], task['task'])
    slug = name.replace(' ', '')
    n = 1
    while os.path.exists(os.path.join(RUNS, slug, f'run_{n}')):
        n += 1
    rundir = os.path.join(RUNS, slug, f'run_{n}')
    os.makedirs(rundir)

    base, v1 = PROXY.rsplit('/', 1)
    env = dict(os.environ, OPENAI_API_KEY='dummy',
               BASE_URL=f'{base}/t/cd_{slug}_run{n}/{v1}')
    print(f'[{slug}] run_{n} starting', flush=True)
    t0 = time.time()
    with open(os.path.join(rundir, 'console.txt'), 'w') as log:
        try:
            rc = subprocess.run(
                [sys.executable, 'run.py', '--task', task['task_prompt'],
                 '--name', name, '--model', 'GPT_4O', '--config', 'Default'],
                cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT,
                timeout=TIMEOUT).returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
    dur = time.time() - t0

    # archive the WareHouse dir this run produced
    produced = [d for d in glob.glob(
        os.path.join(REPO, 'WareHouse', f'{name}_DefaultOrganization_*'))
        if os.path.getmtime(d) >= t0 - 5]
    wh = max(produced, key=os.path.getmtime) if produced else None
    if wh:
        shutil.copytree(wh, os.path.join(rundir, 'warehouse'))

    result = dict(task=task['task'], project_name=name, run=n, rc=rc,
                  seconds=round(dur, 1), warehouse=wh and os.path.basename(wh),
                  original_solved=task['solved'],
                  cat2_likelihood_screened=task.get('cat2_likelihood_screened'))
    with open(os.path.join(rundir, 'result.json'), 'w') as f:
        json.dump(result, f, indent=1)
    print(f'[{slug}] rc={rc} {dur:.0f}s warehouse={result["warehouse"]}', flush=True)
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
        t for t in TASKS
        if ALIASES.get(t['task'], t['task']).replace(' ', '') in args
        or t['task'] in args]
    if args != ['--all'] and len(sel) != len(args):
        sys.exit(f'unmatched task names; matched {[t["task"] for t in sel]}')
    if par == 1:
        results = [run_one(t) for t in sel]
    else:
        from concurrent.futures import ThreadPoolExecutor  # run_one is subprocess-bound
        with ThreadPoolExecutor(max_workers=par) as ex:
            results = list(ex.map(run_one, sel))
    print(json.dumps(results, indent=1))


if __name__ == '__main__':
    main()
