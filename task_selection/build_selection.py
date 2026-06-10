"""Build the task selection for reproducing ChatDev (1.0) and Magentic-One failures.

Sources:
- ChatDev: human annotations recovered from MAST repo git history
  (`git show 84a56a8^:annotations.csv`, deleted in commit 84a56a8). 32 game tasks,
  old-taxonomy columns mapped to final MAST modes. Task prompts come from the MAD
  HF dataset trajectories (project_name -> **task_prompt**).
- Magentic-One: local traces in mast_repo/traces/MagenticOne_GAIA. Success is
  computed by comparing the trace's FINAL ANSWER against expected_answer.txt.

NOTE: the per-trace `mast_annotation` field in HF mcemri/MAD (both revisions) is
broken — only 206 unique annotation rows exist for 1242 traces and the annotation
is purely a function of the row index. Do not use it.
"""
import json, os, re, subprocess, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAST = os.path.join(ROOT, 'mast_repo')

# ---------------------------------------------------------------- ChatDev ----
CSV = os.path.join(HERE, 'mast_human_annotations_recovered.csv')
if not os.path.exists(CSV):
    csv_text = subprocess.run(['git', '-C', MAST, 'show', '84a56a8^:annotations.csv'],
                              capture_output=True, text=True, check=True).stdout
    with open(CSV, 'w') as f:
        f.write(csv_text)
df = pd.read_csv(CSV)
cd = df[df['MultiAgentSystem Name'] == 'ChatDev']

# old annotation columns -> final MAST failure modes
COLMAP = {
    'Trajectory restart': '2.1', 'Conversation repetition': '2.1',
    'Fail to elicit clarification': '2.2',
    'Derailing from task objectives': '2.3',
    'Withholding relevant information': '2.4',
    'Ignoring good suggestions from other agent': '2.5',
    'Misalignment between internal thoughts and response message': '2.6',
    'Poor adherence to specified constraints': '1.1',
    'Step repetition': '1.3',
    'Unaware of stopping conditions': '1.4',
    'Evaluator agent fails to be critical': '3.2',
    'No attempt to verify outcome': '3.3',
}

def truthy(v):
    return str(v).strip().upper() == 'TRUE'

human = {}
for _, r in cd.iterrows():
    modes = sorted({m for c, m in COLMAP.items() if c in cd.columns and truthy(r[c])})
    human[r['Task ID (Specific to MAS)']] = dict(
        solved=str(r['Is the task Successfully solved (in spite of inefficiencies)']).strip(),
        modes=modes, cat2=[m for m in modes if m.startswith('2')],
        annotator_note=str(r['Freeform Text Annotation by Human Annotator']).strip(),
    )

# task prompts from MAD trajectories
from huggingface_hub import hf_hub_download
mad = json.load(open(hf_hub_download(repo_id='mcemri/MAD', filename='MAD_full_dataset.json',
                                     repo_type='dataset')))
prompts = {}
for rec in mad:
    if rec['mas_name'] != 'ChatDev':
        continue
    traj = rec['trace']['trajectory']
    name = re.search(r'\*\*project_name\*\*:?\s*(.+)', traj)
    prompt = re.search(r'\*\*task_prompt\*\*:?\s*(.+)', traj)
    if name and prompt:
        prompts[name.group(1).strip()] = prompt.group(1).strip()

ALIASES = {  # human CSV name -> MAD project_name
    'TicTacToe (with display)': 'TicTacToe', 'The Crossword': 'TheCrossword',
    'Connections': 'ConnectionsNYT', 'Strands': 'StrandsNYT',
}
def find_prompt(task):
    name = ALIASES.get(task, task)
    if name in prompts:
        return prompts[name]
    cands = [k for k in prompts if k.replace(' ', '').lower() == name.replace(' ', '').lower()]
    return prompts[cands[0]] if len(cands) == 1 else None

# selection: all human cat2 tasks, then failed tasks, then solved controls
# (TypingSpeedGame, Hangman, WebCalculator, UCBerkeleyWebsite have no matching
#  task prompt in MAD, so equivalent failed/solved tasks are used instead)
SELECT = (
    [t for t, h in human.items() if h['cat2']]
    + ['Checkers', 'The Crossword', 'Connections', 'MonopolyGo', 'CandyCrush',
       'TextBasedSpaceInvaders', 'DouDizhuPoker', 'Strands', 'Tiny Rouge']  # solved=FALSE
    + ['Gomoku', 'Pong', 'ConnectFour']  # solved=TRUE controls
)
chatdev_sel = []
for t in SELECT:
    h = human[t]
    p = find_prompt(t)
    chatdev_sel.append(dict(task=t, task_prompt=p, **h))

# ------------------------------------------------------------- Magentic ----
GAIA = os.path.join(MAST, 'traces', 'MagenticOne_GAIA')
STANDARD = {'global_finalize.sh', 'requirements.txt', 'timestamp.txt', 'expected_answer.txt',
            'config.yaml', 'prompt.txt', 'run.sh', 'console_log.txt', 'scenario.py',
            'global_init.sh', 'logs'}

def norm_ans(s):
    s = s.strip().lower()
    s = re.sub(r'[,$%]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s

gaia_tasks = []
for lvl in (1, 2, 3):
    d = os.path.join(GAIA, f'gaia_validation_level_{lvl}__MagenticOne')
    for uuid in sorted(os.listdir(d)):
        p = os.path.join(d, uuid, '0')
        if not os.path.isdir(p):
            continue
        log = open(os.path.join(p, 'console_log.txt'), errors='replace').read()
        m = re.findall(r'FINAL ANSWER:\s*(.+)', log)
        final = m[-1].strip() if m else None
        expected = open(os.path.join(p, 'expected_answer.txt')).read().strip()
        attachments = [f for f in os.listdir(p)
                       if f not in STANDARD and not f.startswith(('tmp_code_', 'output', '.'))]
        gaia_tasks.append(dict(
            uuid=uuid, level=lvl,
            question=open(os.path.join(p, 'prompt.txt')).read().strip(),
            expected_answer=expected, magentic_final_answer=final,
            attachments=attachments,
            success=final is not None and norm_ans(final) == norm_ans(expected),
            trace_dir=os.path.relpath(p, ROOT),
        ))

# near-misses: original answer is semantically right, fails only on exact-match
# normalization ("Brunei Darussalam" vs "Brunei") — useless as failure cases
NEAR_MISS = {'0a3cd321-3e76-4622-911b-0fda2e5d6b1a'}

failed = [t for t in gaia_tasks if not t['success'] and t['uuid'] not in NEAR_MISS]
succeeded = [t for t in gaia_tasks if t['success']]
print(f'GAIA local tasks: {len(gaia_tasks)}; failed: {len(failed)}; succeeded: {len(succeeded)}')

# selection: failed tasks, no attachments preferred, across levels + 2 controls
def take(pool, n, pred):
    out = [t for t in pool if pred(t)][:n]
    for t in out:
        pool.remove(t)
    return out

pool = list(failed)
magentic_sel = (
    take(pool, 5, lambda t: t['level'] == 1 and not t['attachments'])
    + take(pool, 5, lambda t: t['level'] == 2 and not t['attachments'])
    + take(pool, 1, lambda t: t['level'] == 3 and not t['attachments'])
    # attachment tasks must be text-parseable (no images: gpt-5.4-mini via
    # Perplexity has no vision)
    + take(pool, 2, lambda t: t['level'] == 2 and t['attachments'] and
           not any(a.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) for a in t['attachments']))
)
magentic_sel += [t for t in succeeded if not t['attachments']][:2]  # controls

json.dump(chatdev_sel, open(os.path.join(HERE, 'chatdev_tasks.json'), 'w'), indent=1)
json.dump(magentic_sel, open(os.path.join(HERE, 'magentic_gaia_tasks.json'), 'w'), indent=1)
json.dump(gaia_tasks, open(os.path.join(HERE, 'magentic_gaia_all_outcomes.json'), 'w'), indent=1)

print(f'ChatDev selected: {len(chatdev_sel)} '
      f'(missing prompts: {sum(1 for x in chatdev_sel if not x["task_prompt"])})')
for x in chatdev_sel:
    print(f'  {x["task"]:<26} solved={x["solved"]:<6} cat2={",".join(x["cat2"]) or "-"}')
print(f'Magentic selected: {len(magentic_sel)}')
for x in magentic_sel:
    att = ' +att' if x['attachments'] else ''
    print(f'  L{x["level"]} {x["uuid"][:8]} success={x["success"]}{att}  {x["question"][:80]}')
