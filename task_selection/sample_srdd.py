"""Sample SRDD tasks for the MacNet-native evaluation (macnet-srdd config).

SRDD (Software Requirement Description Dataset, from the MacNet paper's own
evaluation) lives on the chatdev1.0 branch of OpenBMB/ChatDev:
  https://raw.githubusercontent.com/OpenBMB/ChatDev/chatdev1.0/SRDD/data/data_attribute_format.csv
(cached at task_selection/data/srdd_data_attribute_format.csv, gitignored).
1,200 tasks as Name,Description,Category; the Category values match the
SRDD_Profile/<Category>/ persona dirs shipped on the macnet branch, which
MacNet's --type flag consumes.

Selection: seeded (seed=0) sample of N_TASKS distinct categories, one task
per category, so the 10 runs cover 10 different software domains.

Writes task_selection/macnet_srdd_tasks.json with fields mirroring
chatdev_tasks.json where applicable (task, task_prompt) plus category/type.
solved is null: SRDD has no ground-truth outcome; success comes from the
judge's task_success verdict.

Usage: python task_selection/sample_srdd.py
"""
import csv, json, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, 'data', 'srdd_data_attribute_format.csv')
OUT = os.path.join(HERE, 'macnet_srdd_tasks.json')
N_TASKS = 10
SEED = 0


def main():
    rows = list(csv.DictReader(open(CSV, encoding='utf-8')))
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r['Category'], []).append(r)
    rng = random.Random(SEED)
    cats = rng.sample(sorted(by_cat), N_TASKS)
    tasks = []
    for cat in sorted(cats):
        r = rng.choice(sorted(by_cat[cat], key=lambda x: x['Name']))
        tasks.append(dict(task=r['Name'], task_prompt=r['Description'],
                          category=cat, type=cat, solved=None))
    with open(OUT, 'w') as f:
        json.dump(tasks, f, indent=1)
    print(f'wrote {len(tasks)} tasks to {OUT}:')
    for t in tasks:
        print(f"  {t['category']:24s} {t['task']}")


if __name__ == '__main__':
    main()
