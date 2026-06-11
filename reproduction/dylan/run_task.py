"""Run screened MMLU items through NATIVE DyLAN (SALT-NLP/DyLAN).

Uses the paper-default MMLU configuration: 7 role-played agents (Economist,
Doctor, Lawyer, Mathematician, Psychologist, Programmer, Historian), 3 rounds,
listwise ranker activation, 2/3-consensus early stopping. The framework is
unmodified; openai 0.27.6 is pointed at the proxy via OPENAI_API_BASE (the
proxy routes the 0.x /engines/<engine>/chat/completions path).

Tasks come from task_selection/dylan_tasks.json (12 single-model-baseline
failures + 3 passes, see task_selection/screen_dylan.py). One question per
invocation so each run gets a tagged proxy route (/t/dy_<id>_runN/v1) and an
isolated output dir.

The judge input is transcript.txt, rebuilt from DyLAN's own per-round
completion log (out_*/<id>_73.json): every agent's full reply per round, with
deactivation markers, ending with the final answer vs expected.

Usage:
  conda run -n dylan python reproduction/dylan/run_task.py mmlu_formal_logic_3
  conda run -n dylan python reproduction/dylan/run_task.py --all --parallel 4
"""
import ast, csv, glob, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPT = os.path.join(ROOT, 'reproduction', 'dylan_repo', 'code', 'MMLU',
                      'llmlp_listwise_mmlu.py')
RUNS = os.path.join(ROOT, 'reproduction', 'runs', 'dylan')
PROXY = os.environ.get('PROXY_URL', 'http://127.0.0.1:8744/v1')
TIMEOUT = int(os.environ.get('TASK_TIMEOUT', '1800'))

ROLES = ['Economist', 'Doctor', 'Lawyer', 'Mathematician', 'Psychologist',
         'Programmer', 'Historian']


def build_transcript(task, completions, accs_line, dest):
    """Plain-text trace for the judge from DyLAN's completion log."""
    rounds = max((len(c) for c in completions), default=0)
    out = [f"DyLAN listwise MMLU run — 7 agents, {rounds} rounds max, "
           "2/3-consensus early stop",
           f"Subject: {task['subject']}",
           f"Question:\n{task['question']}",
           "Options:\n" + '\n'.join(
               f"  {k}) {task['options'][k]}" for k in 'ABCD'), '']
    for r in range(rounds):
        out.append(f"================ Round {r + 1} ================")
        for k, role in enumerate(ROLES):
            reply = completions[k][r] if r < len(completions[k]) else None
            out.append(f"--- Agent {k + 1} ({role}) ---")
            out.append(reply if reply is not None else
                       "[not activated this round — deactivated by the "
                       "listwise ranker or early stop]")
        out.append('')
    out.append("================ RESULT ================")
    out.append(f"Expected answer: {task['answer']}")
    out.append(f"Exact match: {accs_line}")
    with open(dest, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))


def run_one(task):
    qid = task['id']
    n = 1
    while os.path.exists(os.path.join(RUNS, qid, f'run_{n}')):
        n += 1
    rundir = os.path.join(RUNS, qid, f'run_{n}')
    os.makedirs(rundir)

    qcsv = os.path.join(rundir, 'q.csv')
    with open(qcsv, 'w', newline='') as f:
        csv.writer(f).writerow([task['question']] +
                               [task['options'][k] for k in 'ABCD'] +
                               [task['answer']])

    base, v1 = PROXY.rsplit('/', 1)
    env = dict(os.environ, OPENAI_API_KEY='dummy',
               OPENAI_API_BASE=f'{base}/t/dy_{qid}_run{n}/{v1}')
    print(f'[{qid}] run_{n} starting', flush=True)
    t0 = time.time()
    with open(os.path.join(rundir, 'console.txt'), 'w') as log:
        try:
            rc = subprocess.run(
                [sys.executable, SCRIPT, 'q.csv', qid, 'gpt-3.5-turbo',
                 'out', str(ROLES)],
                cwd=rundir, env=env, stdout=log, stderr=subprocess.STDOUT,
                timeout=TIMEOUT).returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
    dur = time.time() - t0

    # parse DyLAN's own outputs: out_*/<qid>_73.{json,txt}
    exact_match = resp_cnt = ptok = ctok = None
    outdir = glob.glob(os.path.join(rundir, 'out_*'))
    jpath = outdir and os.path.join(outdir[0], f'{qid}_73.json')
    tpath = outdir and os.path.join(outdir[0], f'{qid}_73.txt')
    if tpath and os.path.exists(tpath):
        lines = open(tpath).read().splitlines()
        accs = ast.literal_eval(lines[0].rsplit(' ', 1)[0])
        exact_match = bool(accs[0])
        resp_cnt = int(lines[1].split(' ')[0])
        ptok, ctok = int(lines[4]), int(lines[5])
    if jpath and os.path.exists(jpath):
        completions = json.loads(open(jpath).readline())
        build_transcript(task, completions, exact_match,
                         os.path.join(rundir, 'transcript.txt'))

    result = dict(id=qid, subject=task['subject'], run=n, rc=rc,
                  seconds=round(dur, 1), final_correct=exact_match,
                  expected_answer=task['answer'],
                  baseline_solved=task.get('solved'),
                  resp_count=resp_cnt, prompt_tokens=ptok,
                  completion_tokens=ctok)
    with open(os.path.join(rundir, 'result.json'), 'w') as f:
        json.dump(result, f, indent=1)
    print(f'[{qid}] rc={rc} {dur:.0f}s correct={exact_match} '
          f'calls={resp_cnt}', flush=True)
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
    tasks = json.load(open(os.path.join(ROOT, 'task_selection',
                                        'dylan_tasks.json')))
    sel = tasks if args == ['--all'] else [t for t in tasks
                                           if t['id'] in args]
    if args != ['--all'] and len(sel) != len(args):
        sys.exit(f'unmatched ids; matched {[t["id"] for t in sel]}')
    if par == 1:
        results = [run_one(t) for t in sel]
    else:
        from concurrent.futures import ThreadPoolExecutor  # subprocess-bound
        with ThreadPoolExecutor(max_workers=par) as ex:
            results = list(ex.map(run_one, sel))
    print(json.dumps(results, indent=1))


if __name__ == '__main__':
    main()
