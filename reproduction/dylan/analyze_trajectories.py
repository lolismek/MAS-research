"""Layer-1 mechanical misalignment analysis of DyLAN runs (no LLM calls).

DyLAN logs every agent's full reply per round, so inter-agent information
loss is measurable exactly, without a judge: extract each agent's answer per
round, grade it against gold (is_equiv / letter match), and walk the
trajectory matrix.

MATH-arm subtlety: the debate prompt demands an updated answer AND 1-5 peer
scores "in the form like [[1, 5, 2, ...]]" in the same reply, while the
framework's ans_parser (extract_math_answer) takes the LAST \\boxed{}
expression. Agents that box their scores after their answer get the score
matrix recorded as their "answer" — consensus checks and the final answer
then operate on garbage. We therefore track TWO readings per reply:
  framework answer  what DyLAN itself recorded (drives consensus/final)
  semantic answer   last boxed expression that is NOT a [[...]] score matrix
                    (what the agent actually concluded)

Metrics per run (flip/correction/ever metrics use SEMANTIC answers):
  ever_correct            any agent produced the correct answer in any round
                          -> separates structural loss (system HAD the answer
                          and coordination discarded it) from capability
                          failure (nothing to lose)
  conformity_flips        agent correct in round r, active and wrong in r+1
                          (abandoned a right answer after reading peers --
                          the mechanical analog of MAST 2.5)
  corrections             wrong in r -> correct in r+1 (debate working)
  deactivated_correct     agent's last active-round answer was correct, then
                          the listwise ranker deactivated it while the run
                          continued (ranker-induced information discarding)
  parser_masked           semantic answer correct but framework recorded a
                          score matrix instead (answer destroyed in the
                          framework's own extraction channel)
  per-round correct/active counts, final outcome, rounds used

Usage:
  conda run -n dylan python reproduction/dylan/analyze_trajectories.py
Writes trajectory_analysis.json next to this script and prints a summary.
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'reproduction', 'dylan_repo',
                                'code', 'MMLU'))
from utils import (extract_math_answer, is_equiv, parse_single_choice,  # noqa
                   _strip_string)

SCORE_RE = re.compile(r'^\s*\[\[.*\]\]\s*$')


def all_boxed(s):
    """Every \\boxed{...} content in s, in order (same brace walk as the
    framework's find_math_answer, but not just the last one)."""
    out, i = [], 0
    while True:
        j = s.find('\\boxed', i)
        if j < 0:
            return out
        k = j + len('\\boxed')
        while k < len(s) and s[k] in ' \t':
            k += 1
        if k < len(s) and s[k] == '{':
            depth, a = 1, ''
            for c in s[k + 1:]:
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        break
                a += c
            out.append(a)
            i = k + 1 + len(a)
        else:
            out.append(s[k:].split('$')[0].strip())
            i = k + 1


def semantic_math_answer(reply):
    """Last boxed expression that is not a [[...]] peer-score matrix."""
    cands = [b for b in all_boxed(reply) if not SCORE_RE.match(b)]
    return _strip_string(cands[-1]) if cands else extract_math_answer(reply)

MMLU_ROLES = ['Economist', 'Doctor', 'Lawyer', 'Mathematician',
              'Psychologist', 'Programmer', 'Historian']
MATH_ROLES = ['AlgebraExpert', 'CountingProbabilitySpecialist',
              'GeometryWizard', 'IntermediateAlgebraMaestro',
              'NumberTheoryScholar', 'PrealgebraProdigy', 'PrecalculusGuru']

ARMS = [  # (system, runs dir, task file, roles, answer extractor+grader)
    ('dylan', 'dylan', 'dylan_tasks.json', MMLU_ROLES, 'mmlu'),
    ('dylan-math', 'dylan-math', 'dylan_math_tasks.json', MATH_ROLES, 'math'),
]


def grade(kind, reply, gold):
    """-> {framework answer/correct, semantic answer/correct} | None."""
    if reply is None:
        return None
    if kind == 'math':
        fw = extract_math_answer(reply)
        sem = semantic_math_answer(reply)
        return dict(answer=sem, correct=bool(is_equiv(gold, sem)),
                    fw_answer=fw, fw_correct=bool(is_equiv(gold, fw)))
    ans = parse_single_choice(reply)  # immune to the score-matrix collision
    return dict(answer=ans, correct=ans == gold,
                fw_answer=ans, fw_correct=ans == gold)


def analyze_run(task, rundir, roles, kind):
    jpaths = glob.glob(os.path.join(rundir, 'out_*', '*3.json'))
    if not jpaths:
        return None
    completions = json.loads(open(jpaths[0]).readline())
    res = json.load(open(os.path.join(rundir, 'result.json')))
    gold = task['answer']
    n_rounds = max(len(c) for c in completions)

    # trajectory matrix: traj[agent][round] = grade dict | None
    traj = [[None] * n_rounds for _ in completions]
    for a, rounds in enumerate(completions):
        for r, reply in enumerate(rounds):
            traj[a][r] = grade(kind, reply, gold)

    per_round = [dict(active=sum(1 for a in traj if a[r]),
                      correct=sum(1 for a in traj if a[r] and a[r]['correct']))
                 for r in range(n_rounds)]

    conformity, corrections, deact_correct, masked = [], [], [], []
    for a, rounds in enumerate(traj):
        for r in range(n_rounds):
            cur = rounds[r]
            if cur and cur['correct'] and not cur['fw_correct']:
                masked.append(dict(agent=roles[a], round=r + 1,
                                   semantic=cur['answer'],
                                   framework_recorded=cur['fw_answer']))
        for r in range(n_rounds - 1):
            cur, nxt = rounds[r], rounds[r + 1]
            if cur and nxt:
                if cur['correct'] and not nxt['correct']:
                    conformity.append(dict(agent=roles[a], round=r + 1,
                                           dropped=cur['answer'],
                                           to=nxt['answer']))
                if not cur['correct'] and nxt['correct']:
                    corrections.append(dict(agent=roles[a], round=r + 1))
            # deactivated after answering correctly, while the run went on
            if (cur and cur['correct'] and nxt is None
                    and any(rounds2[r + 1] for rounds2 in traj)):
                deact_correct.append(dict(agent=roles[a],
                                          deactivated_round=r + 2))

    ever = any(c and c['correct'] for rounds in traj for c in rounds)
    return dict(
        id=task['id'], system=None, run=os.path.basename(rundir),
        baseline_solved=task.get('solved'),
        final_correct=res.get('final_correct'),
        rounds_used=sum(1 for pr in per_round if pr['active']),
        calls=res.get('resp_count'), per_round=per_round,
        ever_correct=ever, conformity_flips=conformity,
        corrections=corrections, deactivated_correct=deact_correct,
        parser_masked=masked,
        trajectory=[[(c['answer'] if c else None) for c in rounds]
                    for rounds in traj],
        trajectory_framework=[[(c['fw_answer'] if c else None)
                               for c in rounds] for rounds in traj],
        trajectory_correct=[[(c['correct'] if c else None) for c in rounds]
                            for rounds in traj])


def main():
    report = []
    for system, runsdir, taskfile, roles, kind in ARMS:
        tf = os.path.join(ROOT, 'task_selection', taskfile)
        if not os.path.exists(tf):
            continue
        for task in json.load(open(tf)):
            for rundir in sorted(glob.glob(os.path.join(
                    ROOT, 'reproduction', 'runs', runsdir,
                    task['id'], 'run_*'))):
                rec = analyze_run(task, rundir, roles, kind)
                if rec:
                    rec['system'] = system
                    report.append(rec)

    with open(os.path.join(HERE, 'trajectory_analysis.json'), 'w') as f:
        json.dump(report, f, indent=1)

    for system in dict.fromkeys(r['system'] for r in report):
        recs = [r for r in report if r['system'] == system]
        fails = [r for r in recs if not r['final_correct']]
        print(f"\n=== {system} ({len(recs)} runs) ===")
        print(f"final correct: {sum(bool(r['final_correct']) for r in recs)}"
              f"/{len(recs)}")
        print(f"conformity flips (correct->wrong after seeing peers): "
              f"{sum(len(r['conformity_flips']) for r in recs)}")
        print(f"corrections (wrong->correct): "
              f"{sum(len(r['corrections']) for r in recs)}")
        print(f"ranker deactivated a correct agent: "
              f"{sum(len(r['deactivated_correct']) for r in recs)} events")
        print(f"parser-masked correct answers (framework recorded the "
              f"[[..]] score matrix instead): "
              f"{sum(len(r['parser_masked']) for r in recs)}")
        struct = [r['id'] for r in fails if r['ever_correct']]
        cap = [r['id'] for r in fails if not r['ever_correct']]
        print(f"failures where some agent HAD the right answer "
              f"(structural loss candidates): {len(struct)} {struct}")
        print(f"failures where NO agent ever had it (capability): "
              f"{len(cap)} {cap}")
        for r in recs:
            pr = ' '.join(f"{p['correct']}/{p['active']}"
                          for p in r['per_round'] if p['active'])
            print(f"  {r['id']:44s} final={str(r['final_correct']):5s} "
                  f"rounds={r['rounds_used']} correct/active per round: {pr}")


if __name__ == '__main__':
    main()
