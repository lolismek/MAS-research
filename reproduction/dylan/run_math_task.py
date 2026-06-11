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
import ast, glob, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'reproduction', 'dylan_repo',
                                'code', 'MMLU'))
from utils import extract_math_answer, is_equiv, most_frequent  # noqa: E402

SCRIPT = os.path.join(ROOT, 'reproduction', 'dylan_repo', 'code', 'MMLU',
                      'llmlp_listwise_math.py')
RUNS = os.path.join(ROOT, 'reproduction', 'runs', 'dylan-math')
PROXY = os.environ.get('PROXY_URL', 'http://127.0.0.1:8744/v1')
TIMEOUT = int(os.environ.get('TASK_TIMEOUT', '2400'))

ROLES = ['AlgebraExpert', 'CountingProbabilitySpecialist', 'GeometryWizard',
         'IntermediateAlgebraMaestro', 'NumberTheoryScholar',
         'PrealgebraProdigy', 'PrecalculusGuru']


PREAMBLE = """\
DyLAN listwise MATH run — 7 agents (one specialist per MATH subject), up to \
3 rounds, 2/3-consensus early stop.

How this framework operates (factual context for reading the transcript):
- Round 1: each agent answers independently, activated one at a time in \
random order; once at least 5 agents have answered, the system stops early \
if more than 2/3 of the team's recorded answers agree (compared by \
mathematical equivalence).
- Rounds 2+: each active agent is shown the previous round's replies, and \
the framework's prompt asks it for an updated answer AND a 1-5 score for \
each peer reply "in the form like [[1, 5, 2, ...]]" — both in the same \
reply.
- Before round 3, a separate ranker call (not part of this transcript) \
selects the top 2 round-2 replies; all other agents are deactivated for the \
rest of the run.
- The framework records each agent's answer as the LAST \\boxed{...} \
expression in its reply; consensus checks and the final answer are computed \
over these recorded answers. The recorded answer is shown after each reply \
below as "[framework-recorded answer: ...]".
"""


def system_final_answer(completions, console_path):
    """The run's final answer: the consensus print if one fired, else
    most_frequent over the last round's recorded answers (reproducing
    LLMLP.forward's fallback return)."""
    if os.path.exists(console_path):
        hits = re.findall(r'^Consensus answer: (.*)$',
                          open(console_path, encoding='utf-8',
                               errors='replace').read(), re.M)
        if hits:
            return hits[-1]
    last = [c[-1] for c in completions if c and c[-1] is not None]
    if not last:
        return None
    return most_frequent([extract_math_answer(r) for r in last], is_equiv)[0]


def build_transcript(task, completions, accs_line, dest, final_answer=None):
    """Plain-text trace for the judge from DyLAN's completion log."""
    rounds = max((len(c) for c in completions), default=0)
    out = [PREAMBLE,
           f"Subject: {task['subject']} (level {task['level']})",
           f"Problem:\n{task['problem']}", '']
    for r in range(rounds):
        out.append(f"================ Round {r + 1} ================")
        for k, role in enumerate(ROLES):
            reply = completions[k][r] if r < len(completions[k]) else None
            out.append(f"--- Agent {k + 1} ({role}) ---")
            if reply is None:
                out.append("[not activated this round — deactivated by the "
                           "listwise ranker or early stop]")
            else:
                out.append(reply)
                out.append("[framework-recorded answer: "
                           f"{extract_math_answer(reply)}]")
        out.append('')
    out.append("================ RESULT ================")
    out.append(f"System final answer: {final_answer}")
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
    final_answer = None
    if jpath and os.path.exists(jpath):
        completions = json.loads(open(jpath).readline())
        final_answer = system_final_answer(
            completions, os.path.join(rundir, 'console.txt'))
        build_transcript(task, completions, exact_match,
                         os.path.join(rundir, 'transcript.txt'),
                         final_answer)

    result = dict(id=qid, subject=task['subject'], level=task['level'],
                  run=n, rc=rc, seconds=round(dur, 1),
                  final_correct=exact_match, final_answer=final_answer,
                  expected_answer=task['answer'],
                  baseline_solved=task.get('solved'),
                  resp_count=resp_cnt, prompt_tokens=ptok,
                  completion_tokens=ctok)
    with open(os.path.join(rundir, 'result.json'), 'w') as f:
        json.dump(result, f, indent=1)
    print(f'[{qid}] rc={rc} {dur:.0f}s correct={exact_match} '
          f'calls={resp_cnt}', flush=True)
    return result


def rebuild_transcripts():
    """Regenerate transcript.txt (and result.json's final_answer) for every
    archived run from its own logs — no LLM calls, no re-running."""
    tasks = {t['id']: t for t in json.load(open(os.path.join(
        ROOT, 'task_selection', 'dylan_math_tasks.json')))}
    for rundir in sorted(glob.glob(os.path.join(RUNS, '*', 'run_*'))):
        qid = os.path.basename(os.path.dirname(rundir))
        jpaths = glob.glob(os.path.join(rundir, 'out_*', '*3.json'))
        if qid not in tasks or not jpaths:
            continue
        completions = json.loads(open(jpaths[0]).readline())
        respath = os.path.join(rundir, 'result.json')
        res = json.load(open(respath))
        final_answer = system_final_answer(
            completions, os.path.join(rundir, 'console.txt'))
        build_transcript(tasks[qid], completions, res.get('final_correct'),
                         os.path.join(rundir, 'transcript.txt'),
                         final_answer)
        res['final_answer'] = final_answer
        with open(respath, 'w') as f:
            json.dump(res, f, indent=1)
        print(f'rebuilt {rundir}  final_answer={final_answer!r}')


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if args == ['--rebuild-transcripts']:
        rebuild_transcripts()
        return
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
