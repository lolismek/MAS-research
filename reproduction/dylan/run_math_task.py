"""Run screened MATH level-5 items through NATIVE DyLAN's MATH track.

Same LLMLP listwise machinery as run_task.py (3 rounds, listwise ranker,
2/3-consensus early stop) but qtype math_exp: free-form \\boxed{} answers
graded by the framework's own is_equiv. Free-form answers mean consensus
requires genuine convergence — unlike 4-option MMLU, where wrong agents
collide on the same letter and 13/15 runs early-stopped at round 1.

Team: 7 agents, one per MATH subject, using dylan_repo's own ROLE_MAP_MATH
personas (the role map ships exactly one specialist per Hendrycks MATH
subject). This keeps team size identical to the MMLU arm; the paper's MATH
experiments used 4 agents, so the 7-specialist team is a documented
deviation chosen for richer inter-agent traces.

Tasks come from task_selection/dylan_math_tasks.json (12 single-model
baseline failures + 3 passes, see task_selection/screen_dylan_math.py).
Each run writes a one-problem Hendrycks-format dir (problems/1.json) since
llmlp_listwise_math.py reads MATH problems from per-file JSON.

Usage:
  conda run -n dylan python reproduction/dylan/run_math_task.py math500_algebra_1352
  conda run -n dylan python reproduction/dylan/run_math_task.py --all --parallel 4
"""
import ast, glob, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPT = os.path.join(ROOT, 'reproduction', 'dylan_repo', 'code', 'MMLU',
                      'llmlp_listwise_math.py')
RUNS = os.path.join(ROOT, 'reproduction', 'runs', 'dylan-math')
PROXY = os.environ.get('PROXY_URL', 'http://127.0.0.1:8744/v1')
TIMEOUT = int(os.environ.get('TASK_TIMEOUT', '2400'))

ROLES = ['AlgebraExpert', 'CountingProbabilitySpecialist', 'GeometryWizard',
         'IntermediateAlgebraMaestro', 'NumberTheoryScholar',
         'PrealgebraProdigy', 'PrecalculusGuru']


def build_transcript(task, completions, accs_line, dest):
    """Plain-text trace for the judge from DyLAN's completion log."""
    rounds = max((len(c) for c in completions), default=0)
    out = [f"DyLAN listwise MATH run — {len(ROLES)} agents (one specialist "
           f"per MATH subject), {rounds} rounds max, 2/3-consensus early stop",
           f"Subject: {task['subject']} (level {task['level']})",
           f"Problem:\n{task['problem']}", '']
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
    out.append(f"Exact match (is_equiv): {accs_line}")
    with open(dest, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))


def run_one(task):
    qid = task['id']
    n = 1
    while os.path.exists(os.path.join(RUNS, qid, f'run_{n}')):
        n += 1
    rundir = os.path.join(RUNS, qid, f'run_{n}')
    os.makedirs(os.path.join(rundir, 'problems'))

    # one-problem Hendrycks MATH dir for get_math_qa_pairs
    with open(os.path.join(rundir, 'problems', '1.json'), 'w') as f:
        json.dump(dict(problem=task['problem'],
                       level=f"Level {task['level']}",
                       type=task['subject'],
                       solution=task['solution']), f)

    base, v1 = PROXY.rsplit('/', 1)
    env = dict(os.environ, OPENAI_API_KEY='dummy',
               OPENAI_API_BASE=f'{base}/t/dy_math_{qid}_run{n}/{v1}')
    print(f'[{qid}] run_{n} starting', flush=True)
    t0 = time.time()
    with open(os.path.join(rundir, 'console.txt'), 'w') as log:
        try:
            rc = subprocess.run(
                [sys.executable, SCRIPT, 'problems', '1', '1', qid,
                 'gpt-3.5-turbo', 'out', str(ROLES)],
                cwd=rundir, env=env, stdout=log, stderr=subprocess.STDOUT,
                timeout=TIMEOUT).returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
    dur = time.time() - t0

    # parse DyLAN's own outputs: out_*/{qid}_1_1_73.{json,txt}
    # (the .txt tail differs from the MMLU track: tokens are "pt ct" on one
    # line instead of two separate lines)
    exact_match = resp_cnt = ptok = ctok = None
    outdir = glob.glob(os.path.join(rundir, 'out_*'))
    jpath = outdir and os.path.join(outdir[0], f'{qid}_1_1_{len(ROLES)}3.json')
    tpath = outdir and os.path.join(outdir[0], f'{qid}_1_1_{len(ROLES)}3.txt')
    if tpath and os.path.exists(tpath):
        lines = open(tpath).read().splitlines()
        accs = ast.literal_eval(lines[0].rsplit(' ', 1)[0])
        exact_match = bool(accs[0])
        resp_cnt = int(lines[1].split(' ')[0])
        ptok, ctok = (int(x) for x in lines[4].split(' '))
    if jpath and os.path.exists(jpath):
        completions = json.loads(open(jpath).readline())
        build_transcript(task, completions, exact_match,
                         os.path.join(rundir, 'transcript.txt'))

    result = dict(id=qid, subject=task['subject'], level=task['level'],
                  run=n, rc=rc, seconds=round(dur, 1),
                  final_correct=exact_match, expected_answer=task['answer'],
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
                                        'dylan_math_tasks.json')))
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
