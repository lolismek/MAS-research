"""Screen hard MMLU items for the DyLAN evaluation.

DyLAN has no original MAST traces, so cat-2 priors can't be screened from
history like chatdev_tasks/magentic_gaia_tasks. Instead we screen for
single-model difficulty: run every candidate once through gpt-5.4-mini (the
same model the MAS will use, via the proxy) and select questions the bare
model gets wrong — failure traces are what elicit MAST modes — plus a few
baseline passes as controls (analog of the solved controls in the other
task sets).

Candidate pool: 20 test questions from each of 6 hard MMLU subjects
(120 total), fetched from the HF datasets server (cais/mmlu, test split)
and cached under task_selection/data/ (gitignored).

Outputs:
  dylan_screen_results.json - outcome for every candidate (analog of
                              magentic_gaia_all_outcomes.json)
  dylan_tasks.json          - N_FAIL baseline failures + N_PASS passes,
                              spread across subjects

Cost: 120 single calls ~ $0.5. Requires the proxy running on :8744
(calls are tagged dy_screen in calls.jsonl).

Usage: python task_selection/screen_dylan.py [--limit N]   # N per subject
"""
import json, os, re, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
PROXY = os.environ.get('PROXY_URL', 'http://127.0.0.1:8744')

SUBJECTS = ['college_mathematics', 'abstract_algebra', 'formal_logic',
            'college_physics', 'econometrics', 'professional_law']
PER_SUBJECT = 20
N_FAIL, N_PASS = 12, 3
LETTERS = 'ABCD'

PROMPT = """The following is a multiple choice question. Think step by step \
and then answer with only a single letter (A, B, C or D) on the last line, \
in the form "Answer: X".

{q}

A) {a}
B) {b}
C) {c}
D) {d}"""


def fetch_subject(subject, limit):
    """20 test rows via the HF datasets-server rows API, cached on disk."""
    cache = os.path.join(DATA, f'mmlu_{subject}.json')
    if os.path.exists(cache):
        return json.load(open(cache))[:limit]
    url = ('https://datasets-server.huggingface.co/rows?' +
           urllib.parse.urlencode(dict(dataset='cais/mmlu', config=subject,
                                       split='test', offset=0,
                                       length=PER_SUBJECT)))
    rows = json.load(urllib.request.urlopen(url))['rows']
    items = [dict(question=r['row']['question'],
                  options={k: c for k, c in zip(LETTERS, r['row']['choices'])},
                  answer=LETTERS[r['row']['answer']])
             for r in rows]
    os.makedirs(DATA, exist_ok=True)
    json.dump(items, open(cache, 'w'), indent=1)
    return items[:limit]


def ask_baseline(item):
    body = json.dumps(dict(
        model='gpt-4o',  # aliased to gpt-5.4-mini by the proxy
        temperature=0,
        messages=[dict(role='user', content=PROMPT.format(
            q=item['question'], a=item['options']['A'],
            b=item['options']['B'], c=item['options']['C'],
            d=item['options']['D']))])).encode()
    req = urllib.request.Request(
        f'{PROXY}/t/dy_screen/v1/chat/completions', data=body,
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Bearer dummy'})
    reply = json.load(urllib.request.urlopen(req, timeout=300))
    text = reply['choices'][0]['message']['content'] or ''
    m = re.findall(r'[Aa]nswer:?\s*\**([ABCD])\b', text)
    pred = m[-1] if m else None
    if pred is None:  # fall back to the last standalone letter
        m = re.findall(r'\b([ABCD])\b', text)
        pred = m[-1] if m else None
    return pred, text


def main():
    limit = PER_SUBJECT
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
    results = []
    for subject in SUBJECTS:
        for i, item in enumerate(fetch_subject(subject, limit)):
            pred, _ = ask_baseline(item)
            ok = pred == item['answer']
            results.append(dict(id=f'mmlu_{subject}_{i}', subject=subject,
                                baseline_pred=pred, baseline_correct=ok,
                                **item))
            print(f"{results[-1]['id']:34s} gold={item['answer']} "
                  f"pred={pred} {'PASS' if ok else 'FAIL'}", flush=True)
    with open(os.path.join(HERE, 'dylan_screen_results.json'), 'w') as f:
        json.dump(results, f, indent=1)

    fails = [r for r in results if not r['baseline_correct']]
    passes = [r for r in results if r['baseline_correct']]
    # round-robin over subjects so the selection isn't all professional_law
    def spread(pool, n):
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
    tasks = [dict(id=t['id'], subject=t['subject'], question=t['question'],
                  options=t['options'], answer=t['answer'], solved=t['solved'],
                  baseline_model='gpt-5.4-mini', baseline_pred=t['baseline_pred'],
                  cat2_likelihood_screened=None,
                  screen_note='single-model baseline screen (see screen_dylan.py); '
                              'no original MAS trace exists for cat-2 screening')
             for t in sel]
    with open(os.path.join(HERE, 'dylan_tasks.json'), 'w') as f:
        json.dump(tasks, f, indent=1)
    print(f'\n{len(fails)}/{len(results)} baseline failures; wrote '
          f'{len(tasks)} tasks ({N_FAIL} fail + {N_PASS} pass) to dylan_tasks.json')


if __name__ == '__main__':
    main()
