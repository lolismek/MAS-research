"""Generate the data-driven parts of the LaTeX report from judged JSONs.

Emits (into this directory):
  gen_outcomes.tex   - per-system outcome tables (original vs reproduction)
  gen_modes.tex      - MAST mode frequency table
  gen_trends.tex     - stage-A finding clusters table
  gen_appendix.tex   - one subsection per case (30), from both judge tiers

Run: conda run -n base python reproduction/report/make_report.py
then compile main.tex (tectonic/pdflatex/Overleaf).
"""
import glob, json, os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MODES = ['1.1', '1.2', '1.3', '1.4', '1.5', '2.1', '2.2', '2.3', '2.4',
         '2.5', '2.6', '3.1', '3.2', '3.3']
MODE_NAMES = {
    '1.1': 'Disobey Task Specification', '1.2': 'Disobey Role Specification',
    '1.3': 'Step Repetition', '1.4': 'Loss of Conversation History',
    '1.5': 'Unaware of Termination Conditions', '2.1': 'Conversation Reset',
    '2.2': 'Fail to Ask for Clarification', '2.3': 'Task Derailment',
    '2.4': 'Information Withholding', '2.5': "Ignored Other Agent's Input",
    '2.6': 'Action-Reasoning Mismatch', '3.1': 'Premature Termination',
    '3.2': 'No or Incorrect Verification', '3.3': 'Weak Verification'}
ARTIFACT_KINDS = {'model mismatch', 'logging failure', 'timestamp mismatch',
                  'timestamp inconsistency', 'timestamp anomaly',
                  'telemetry anomaly', 'stale metadata'}
UNI = {'—': '---', '–': '--', '‘': "'", '’': "'", '“': "``", '”': "''",
       '→': r'$\rightarrow$', '←': r'$\leftarrow$',
       '↔': r'$\leftrightarrow$', '¬': r'$\lnot$', '≥': r'$\geq$',
       '≤': r'$\leq$', '×': r'$\times$', '°': r'$^{\circ}$', '…': '...',
       '✓': r'\checkmark{}', '∨': r'$\lor$', '∧': r'$\land$',
       'é': r"\'e", 'á': r"\'a", 'ö': r'\"o', 'ü': r'\"u'}


def esc(s):
    if s is None:
        return ''
    s = str(s).replace('\\', '\x00')
    s = s.replace('{', r'\{').replace('}', r'\}')
    for a, b in [('&', r'\&'), ('%', r'\%'), ('$', r'\$'), ('#', r'\#'),
                 ('_', r'\_')]:
        s = s.replace(a, b)
    s = s.replace('~', r'\textasciitilde{}').replace('^', r'\textasciicircum{}')
    s = s.replace('\x00', r'\textbackslash{}')
    for a, b in UNI.items():
        s = s.replace(a, b)
    return ''.join(ch if ord(ch) < 128 else '?' for ch in s)


def load(era='new'):
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'reproduction', 'judged',
                                           era, '*', '*.json'))):
        out.append(json.load(open(f)))
    return out


recs = load('new')
SYSTEMS = [('chatdev', 'ChatDev'), ('magentic', 'Magentic'),
           ('macnet-chain', 'MacNet-chain'), ('macnet-mlp', 'MacNet-mlp'),
           ('macnet-net', 'MacNet-net'), ('macnet-srdd', 'MacNet-SRDD'),
           ('dylan', 'DyLAN')]
bucket = {k: sorted([r for r in recs if r['meta']['system'] == k],
                    key=lambda r: r['meta']['id']) for k, _ in SYSTEMS}
present = [(k, d) for k, d in SYSTEMS if bucket[k]]
cd, mag = bucket['chatdev'], bucket['magentic']
cd_tasks = {t['task']: t for t in json.load(open(
    os.path.join(ROOT, 'task_selection', 'chatdev_tasks.json')))}
mag_tasks = {t['uuid'][:8]: t for t in json.load(open(
    os.path.join(ROOT, 'task_selection', 'magentic_gaia_tasks.json')))}


def opt_tasks(fname, key):
    p = os.path.join(ROOT, 'task_selection', fname)
    return ({t[key]: t for t in json.load(open(p))}
            if os.path.exists(p) else {})


srdd_tasks = opt_tasks('macnet_srdd_tasks.json', 'task')
dylan_tasks = opt_tasks('dylan_tasks.json', 'id')


def judged_by_task(system):
    """task name -> judge pass/fail for the latest run of each task."""
    out = {}
    for r in bucket[system]:
        out[r['meta']['task']] = ('pass' if r['stage_b'].get('task_success')
                                  else 'fail')
    return out

# ------------------------------------------------------------- outcomes ----
with open(os.path.join(HERE, 'gen_outcomes.tex'), 'w') as f:
    f.write('\\begin{table}[h]\\centering\\small\n'
            '\\begin{tabular}{llcc}\\toprule\n'
            'Task & cat-2 prior & GPT-4o (orig.) & gpt-5.4-mini (repro.)\\\\\n'
            '\\midrule\n\\multicolumn{4}{l}{\\textit{ChatDev '
            '(success per human annotation / per our judge)}}\\\\\n')
    for r in cd:
        m = r['meta']
        lk = m.get('cat2_screened') or 'control'
        o = 'pass' if m['original_solved'] == 'TRUE' else 'fail'
        n = 'pass' if r['stage_b'].get('task_success') else 'fail'
        f.write(f"{esc(m['task'])} & {lk} & {o} & {n}\\\\\n")
    f.write('\\midrule\n\\multicolumn{4}{l}{\\textit{Magentic-One '
            '(success by normalized exact match on GAIA answer)}}\\\\\n')
    for r in mag:
        m = r['meta']
        t = mag_tasks[m['uuid'][:8]]
        lk = t.get('cat2_likelihood_screened') or 'control'
        o = 'pass' if m['original_success'] else 'fail'
        n = 'pass' if m.get('new_exact_match') else 'fail'
        f.write(f"{m['uuid'][:8]} (L{t['level']}) & {lk} & {o} & {n}\\\\\n")
    f.write('\\bottomrule\\end{tabular}\n'
            '\\caption{Per-task outcomes, original MAST runs (GPT-4o) vs.\\ '
            'our reproduction (gpt-5.4-mini).}\\label{tab:outcomes}\n'
            '\\end{table}\n')

    # architecture comparison on identical tasks: ChatDev vs MacNet topologies
    mn_cfgs = [(f'macnet-{c}', f'MacNet-{c}') for c in ('chain', 'mlp', 'net')
               if bucket[f'macnet-{c}']]
    if mn_cfgs:
        verdicts = {k: judged_by_task(k) for k, _ in mn_cfgs}
        f.write('\n\\begin{table}[h]\\centering\\small\n'
                f"\\begin{{tabular}}{{ll{'c' * (1 + len(mn_cfgs))}}}\\toprule\n"
                'Task & cat-2 prior & ChatDev & ' +
                ' & '.join(d for _, d in mn_cfgs) + '\\\\\n\\midrule\n')
        for r in cd:
            m = r['meta']
            lk = m.get('cat2_screened') or 'control'
            n = 'pass' if r['stage_b'].get('task_success') else 'fail'
            f.write(f"{esc(m['task'])} & {lk} & {n} & " + ' & '.join(
                verdicts[k].get(m['task'], '--') for k, _ in mn_cfgs) +
                '\\\\\n')
        f.write('\\bottomrule\\end{tabular}\n'
                '\\caption{Same 15 tasks, same model (gpt-5.4-mini), '
                'different coordination structures: ChatDev waterfall vs.\\ '
                'MacNet chain (10 nodes), mlp (8 nodes, dense 4-2-2 layers, '
                'working aggregation), and net (8 nodes, complete DAG; '
                'aggregation structurally inert at the pinned commit). '
                'All verdicts per our judge.}\\label{tab:macnet-outcomes}\n'
                '\\end{table}\n')

    if bucket['macnet-srdd']:
        f.write('\n\\begin{table}[h]\\centering\\small\n'
                '\\begin{tabular}{llc}\\toprule\n'
                'Task & SRDD category & MacNet-chain (judge)\\\\\n\\midrule\n')
        for r in bucket['macnet-srdd']:
            m = r['meta']
            n = 'pass' if r['stage_b'].get('task_success') else 'fail'
            f.write(f"{esc(m['task'])} & "
                    f"{esc(m.get('category'))} & {n}\\\\\n")
        f.write('\\bottomrule\\end{tabular}\n'
                '\\caption{MacNet on its native SRDD tasks (chain, 10 '
                'nodes).}\\label{tab:srdd-outcomes}\n\\end{table}\n')

    if bucket['dylan']:
        f.write('\n\\begin{table}[h]\\centering\\small\n'
                '\\begin{tabular}{llccc}\\toprule\n'
                'Item & Subject & baseline & DyLAN (exact match) & '
                'judge\\\\\n\\midrule\n')
        for r in bucket['dylan']:
            m = r['meta']
            b = 'pass' if m.get('baseline_solved') else 'fail'
            n = 'pass' if m.get('new_exact_match') else 'fail'
            j = 'pass' if r['stage_b'].get('task_success') else 'fail'
            f.write(f"{esc(m['id'].replace('mmlu_', '').rsplit('_run', 1)[0])}"
                    f" & {esc(m.get('subject', '').replace('_', ' '))}"
                    f" & {b} & {n} & {j}\\\\\n")
        f.write('\\bottomrule\\end{tabular}\n'
                '\\caption{DyLAN (7 agents, listwise, 3 rounds) on screened '
                'MMLU items. baseline = single gpt-5.4-mini call at '
                'screening time; outcome = exact match on the gold answer '
                '(judge verdict shown for comparison).}'
                '\\label{tab:dylan-outcomes}\n\\end{table}\n')

# ---------------------------------------------------------------- modes ----
with open(os.path.join(HERE, 'gen_modes.tex'), 'w') as f:
    cols = 'c' * len(present)
    f.write('\\begin{table}[h]\\centering\\small\n'
            f'\\begin{{tabular}}{{ll{cols}}}\\toprule\n'
            'Mode & Name & ' +
            ' & '.join(f'{d} (n={len(bucket[k])})' for k, d in present) +
            '\\\\\n\\midrule\n')
    for mcode in MODES:
        counts = ' & '.join(str(sum(
            1 for r in bucket[k] if r['stage_b']['modes'][mcode]['present']))
            for k, _ in present)
        f.write(f'{mcode} & {esc(MODE_NAMES[mcode])} & {counts}\\\\\n')
    f.write('\\bottomrule\\end{tabular}\n'
            '\\caption{MAST failure-mode incidence per system (gpt-5.5 '
            'judge, evidence-quote required per flag). '
            '2.1/2.2 are lower bounds (Section~\\ref{sec:taxonomy}).}'
            '\\label{tab:modes}\n\\end{table}\n')

# ---------------------------------------------------------------- trends ----
groups = defaultdict(lambda: defaultdict(set))
for r in recs:
    for fd in r['stage_a'].get('findings', []):
        k = (fd.get('kind') or '?').lower().strip()
        if k not in ARTIFACT_KINDS:
            groups[k][r['meta']['system']].add(r['meta']['id'])
with open(os.path.join(HERE, 'gen_trends.tex'), 'w') as f:
    f.write('\\begin{table}[h]\\centering\\small\n'
            f"\\begin{{tabular}}{{l{'c' * len(present)}}}\\toprule\n"
            'Judge-coined finding cluster & ' +
            ' & '.join(d for _, d in present) + '\\\\\n\\midrule\n')
    rows = sorted(groups.items(),
                  key=lambda kv: -sum(len(v) for v in kv[1].values()))
    for k, by in rows:
        tot = sum(len(v) for v in by.values())
        if tot < 3:
            continue
        f.write(f"{esc(k)} & " + ' & '.join(
            str(len(by.get(s, []))) for s, _ in present) + '\\\\\n')
    f.write('\\bottomrule\\end{tabular}\n'
            '\\caption{Recurring open-ended (taxonomy-free) finding clusters '
            'across the reproduced traces; counts are distinct traces. '
            'Reproduction-harness artifacts excluded.}\\label{tab:trends}\n'
            '\\end{table}\n')

# -------------------------------------------------------------- appendix ----
def case(r, head, taskdesc, outcome):
    b = r['stage_b']
    flagged = [m for m in MODES if b['modes'][m]['present']]
    probs = [fd for fd in r['stage_a'].get('findings', [])
             if not fd.get('possibly_innocent')
             and (fd.get('kind') or '').lower() not in ARTIFACT_KINDS]
    out = [f'\\subsection*{{{esc(head)}}}\n',
           f'\\textbf{{Task.}} {esc(taskdesc)}\n\n',
           f'\\textbf{{Outcome.}} {esc(outcome)}\n\n',
           f"\\textbf{{MAST modes (judge).}} {esc(', '.join(flagged))}\n\n",
           f"\\textbf{{Run narrative (judge, tier~1).}} "
           f"{esc(r['stage_a'].get('narrative'))}\n\n",
           f"\\textbf{{Failure summary (judge, tier~2).}} "
           f"{esc(b.get('summary'))}\n\n"]
    if probs:
        out.append('\\textbf{Mechanisms flagged.}\n\\begin{itemize}\n')
        for fd in probs[:6]:
            out.append(f"  \\item \\emph{{{esc(fd.get('kind'))}}}: "
                       f"{esc(fd.get('description'))}\n")
        out.append('\\end{itemize}\n')
    return ''.join(out) + '\n'


with open(os.path.join(HERE, 'gen_appendix.tex'), 'w') as f:
    f.write('\\section{Case briefs: ChatDev}\\label{app:chatdev}\n\n')
    for r in cd:
        m = r['meta']
        t = cd_tasks[m['task']]
        o = ('solved' if m['original_solved'] == 'TRUE' else 'failed')
        n = ('solved' if r['stage_b'].get('task_success') else 'failed')
        outcome = (f'Original GPT-4o run: {o} (human annotation). '
                   f'Reproduction: {n} (judge). '
                   f"Screened cat-2 prior: {m.get('cat2_screened') or 'control'}.")
        f.write(case(r, f"ChatDev: {m['task']}", t['task_prompt'], outcome))
    f.write('\\clearpage\n\\section{Case briefs: Magentic-One (GAIA)}'
            '\\label{app:magentic}\n\n')
    for r in mag:
        m = r['meta']
        t = mag_tasks[m['uuid'][:8]]
        o = 'solved' if m['original_success'] else 'failed'
        n = 'solved' if m.get('new_exact_match') else 'failed'
        outcome = (f'Original GPT-4o run: {o}. Reproduction: {n} '
                   f'(normalized exact match; expected answer: '
                   f'``{t["expected_answer"]}\'\'). Screened cat-2 prior: '
                   f"{t.get('cat2_likelihood_screened') or 'control'}.")
        f.write(case(r, f"Magentic-One {m['uuid'][:8]} (GAIA L{t['level']})",
                     t['question'], outcome))

    for cfg in ('chain', 'mlp', 'net'):
        if not bucket[f'macnet-{cfg}']:
            continue
        f.write(f'\\clearpage\n\\section{{Case briefs: MacNet ({cfg})}}'
                f'\\label{{app:macnet-{cfg}}}\n\n')
        for r in bucket[f'macnet-{cfg}']:
            m = r['meta']
            t = cd_tasks[m['task']]
            n = 'solved' if r['stage_b'].get('task_success') else 'failed'
            outcome = (f"MacNet {cfg} ({m.get('n_nodes')} nodes): {n} "
                       f"(judge). ChatDev original GPT-4o run: "
                       f"{'solved' if t['solved'] == 'TRUE' else 'failed'}. "
                       f"Screened cat-2 prior: "
                       f"{m.get('cat2_screened') or 'control'}.")
            f.write(case(r, f"MacNet-{cfg}: {m['task']}", t['task_prompt'],
                         outcome))
    if bucket['macnet-srdd']:
        f.write('\\clearpage\n\\section{Case briefs: MacNet (SRDD)}'
                '\\label{app:macnet-srdd}\n\n')
        for r in bucket['macnet-srdd']:
            m = r['meta']
            t = srdd_tasks.get(m['task'], {})
            n = 'solved' if r['stage_b'].get('task_success') else 'failed'
            outcome = (f"MacNet chain ({m.get('n_nodes')} nodes): {n} "
                       f"(judge). SRDD category: {m.get('category')}.")
            f.write(case(r, f"MacNet-SRDD: {m['task']}",
                         t.get('task_prompt', ''), outcome))
    if bucket['dylan']:
        f.write('\\clearpage\n\\section{Case briefs: DyLAN (MMLU)}'
                '\\label{app:dylan}\n\n')
        for r in bucket['dylan']:
            m = r['meta']
            tid = m['id'].rsplit('_run', 1)[0]
            t = dylan_tasks.get(tid, {})
            n = 'correct' if m.get('new_exact_match') else 'wrong'
            outcome = (f"DyLAN final answer: {n} (exact match vs gold "
                       f"``{t.get('answer')}''). Single-model baseline at "
                       f"screening: "
                       f"{'correct' if m.get('baseline_solved') else 'wrong'}.")
            f.write(case(r, f"DyLAN: {tid}", t.get('question', ''), outcome))

print('generated gen_outcomes.tex gen_modes.tex gen_trends.tex gen_appendix.tex')
