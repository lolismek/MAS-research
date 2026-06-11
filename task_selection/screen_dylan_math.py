"""Screen hard MATH level-5 items for the DyLAN MATH-track evaluation.

Motivation (follow-up to screen_dylan.py): on 4-option MMLU, agents that are
individually wrong still collide on the same letter often enough to trigger
DyLAN's 2/3-consensus early stop at round 1 — 13/15 of the MMLU runs ended
with 5 calls and no real inter-agent dynamics. MATH answers are free-form
(\\boxed{} expressions graded by the framework's own is_equiv), so consensus
requires genuine convergence and hard items should produce multi-round
debates — the traces this project actually needs.

Candidate pool: the 134 level-5 items of HuggingFaceH4/MATH-500 (the
canonical 500-item sample of the Hendrycks MATH test split), fetched via the
HF datasets-server rows API and cached under task_selection/data/
(gitignored). Baseline = one gpt-5.4-mini call per item through the proxy
(tag dy_math_screen), graded with dylan_repo's own extract_math_answer +
is_equiv so screen grading matches run grading exactly.

Outputs:
  dylan_math_screen_results.json - outcome for every level-5 candidate
  dylan_math_tasks.json          - N_FAIL baseline failures + N_PASS passes,
                                   spread across subjects

Usage: PROXY_URL=http://127.0.0.1:8745 python task_selection/screen_dylan_math.py
"""
import json, os, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, 'data')
PROXY = os.environ.get('PROXY_URL', 'http://127.0.0.1:8744')
N_FAIL, N_PASS = 12, 3

# code/MMLU/utils.py (not code/MATH/util.py, which needs human_eval) — this
# is the module llmlp_listwise_math.py itself grades with
sys.path.insert(0, os.path.join(ROOT, 'reproduction', 'dylan_repo',
                                'code', 'MMLU'))
from utils import extract_math_answer, is_equiv  # noqa: E402

PROMPT = """Solve the following mathematics problem. Think step by step, \
then give the final answer inside \\boxed{{}} on the last line.

Problem: {p}"""


def fetch_math500():
    """All 500 rows (5 pages of 100), cached on disk."""
    cache = os.path.join(DATA, 'math500.json')
    if os.path.exists(cache):
        return json.load(open(cache))
    rows = []
    for offset in range(0, 500, 100):
        url = ('https://datasets-server.huggingface.co/rows?' +
               urllib.parse.urlencode(dict(dataset='HuggingFaceH4/MATH-500',
                                           config='default', split='test',
                                           offset=offset, length=100)))
        rows += [r['row'] for r in
                 json.load(urllib.request.urlopen(url))['rows']]
    os.makedirs(DATA, exist_ok=True)
    json.dump(rows, open(cache, 'w'), indent=1)
    return rows


def ask_baseline(item):
    body = json.dumps(dict(
        model='gpt-4o',  # aliased to gpt-5.4-mini by the proxy
        temperature=0, max_tokens=2048,
        messages=[dict(role='user',
                       content=PROMPT.format(p=item['problem']))])).encode()
    req = urllib.request.Request(
        f'{PROXY}/t/dy_math_screen/v1/chat/completions', data=body,
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Bearer dummy'})
    reply = json.load(urllib.request.urlopen(req, timeout=300))
    text = reply['choices'][0]['message']['content'] or ''
    return extract_math_answer(text), text


def lenient_equiv(gold, pred):
    """is_equiv, plus a guard against formatting-only false negatives
    (e.g. '(-\\sqrt{3}, \\sqrt{3})' vs '(-\\sqrt{3},\\, \\sqrt{3})'): strip
    LaTeX spacing macros and whitespace before comparing. Used only for task
    SELECTION — the runs themselves keep the framework's own is_equiv."""
    if is_equiv(gold, pred):
        return True
    if gold is None or pred is None:
        return False
    strip = lambda s: (s.replace('\\,', '').replace('\\;', '')
                       .replace('\\!', '').replace('\\ ', '')
                       .replace(' ', ''))
    return strip(gold) == strip(pred)


def main():
    reselect = '--reselect' in sys.argv
    respath = os.path.join(HERE, 'dylan_math_screen_results.json')
    if reselect:
        results = json.load(open(respath))
    else:
        pool = [r for r in fetch_math500() if r['level'] == 5]
        print(f'{len(pool)} level-5 candidates', flush=True)
        results = []
        for r in pool:
            # test/precalculus/807.json -> math500_precalculus_807
            qid = 'math500_' + '_'.join(
                r['unique_id'].replace('.json', '').split('/')[1:])
            pred, _ = ask_baseline(r)
            ok = bool(is_equiv(r['answer'], pred))
            results.append(dict(id=qid, subject=r['subject'],
                                level=r['level'], problem=r['problem'],
                                solution=r['solution'], answer=r['answer'],
                                baseline_pred=pred, baseline_correct=ok))
            print(f"{qid:42s} {'PASS' if ok else 'FAIL'}  "
                  f"gold={r['answer']!r} pred={pred!r}", flush=True)
        with open(respath, 'w') as f:
            json.dump(results, f, indent=1)

    for r in results:  # selection-time guard, see lenient_equiv
        if not r['baseline_correct'] and lenient_equiv(r['answer'],
                                                       r['baseline_pred']):
            r['baseline_correct'] = True
            r['reclassified'] = 'formatting-only is_equiv false negative'
            print(f"reclassified as PASS: {r['id']} "
                  f"(gold={r['answer']!r} pred={r['baseline_pred']!r})")

    # reclassified items are excluded from BOTH pools: the run-time grader is
    # the strict is_equiv, so their run outcomes would be equally unreliable
    fails = [r for r in results
             if not r['baseline_correct'] and 'reclassified' not in r]
    passes = [r for r in results
              if r['baseline_correct'] and 'reclassified' not in r]

    def spread(pool, n):  # round-robin over subjects (as screen_dylan.py)
        by_subj, out = {}, []
        for r in pool:
            by_subj.setdefault(r['subject'], []).append(r)
        while len(out) < n and any(by_subj.values()):
            for s in list(by_subj):
                if by_subj[s] and len(out) < n:
                    out.append(by_subj[s].pop(0))
        return out

    sel = ([dict(t, solved=False) for t in spread(fails, N_FAIL)] +
           [dict(t, solved=True) for t in spread(passes, N_PASS)])
    tasks = [dict(id=t['id'], subject=t['subject'], level=t['level'],
                  problem=t['problem'], solution=t['solution'],
                  answer=t['answer'], solved=t['solved'],
                  baseline_model='gpt-5.4-mini', baseline_pred=t['baseline_pred'],
                  cat2_likelihood_screened=None,
                  screen_note='single-model baseline screen '
                              '(see screen_dylan_math.py); free-form answers '
                              'chosen to avoid round-1 consensus-by-collision')
             for t in sel]
    with open(os.path.join(HERE, 'dylan_math_tasks.json'), 'w') as f:
        json.dump(tasks, f, indent=1)
    print(f'\n{len(fails)}/{len(results)} baseline failures; wrote '
          f'{len(tasks)} tasks ({N_FAIL} fail + {N_PASS} pass) to '
          'dylan_math_tasks.json')


if __name__ == '__main__':
    main()
