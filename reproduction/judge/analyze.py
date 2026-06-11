"""Offline explorer for judged traces (no API calls).

Usage (conda run -n base python reproduction/judge/analyze.py ...):
  overview              mode x trace matrix + per-system frequencies
  trace <id-prefix>     one trace in full: narrative, findings, modes+evidence
  mode <X.Y>            every trace flagging that mode, with evidence quotes
  kinds [--system s]    stage-A finding clusters with example descriptions
"""
import glob, json, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MODES = ['1.1', '1.2', '1.3', '1.4', '1.5', '2.1', '2.2', '2.3', '2.4',
         '2.5', '2.6', '3.1', '3.2', '3.3']
# reproduction artifacts, not MAS behavior — excluded from kind clustering
ARTIFACT_KINDS = {'model mismatch', 'logging failure', 'timestamp mismatch',
                  'timestamp inconsistency', 'timestamp anomaly',
                  'telemetry anomaly', 'stale metadata'}


def load(era='new'):
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'reproduction', 'judged',
                                           era, '*', '*.json'))):
        out.append(json.load(open(f)))
    return out


def overview():
    recs = load()
    for system in sorted({r['meta']['system'] for r in recs}):
        rs = [r for r in recs if r['meta']['system'] == system]
        print(f"\n=== {system} (n={len(rs)}) ===")
        print(f"{'trace':<26} " + ' '.join(f'{m:>4}' for m in MODES) + '  success')
        for r in rs:
            row = ' '.join('   x' if r['stage_b']['modes'][m]['present']
                           else '   .' for m in MODES)
            ok = r['stage_b'].get('task_success')
            print(f"{r['meta']['id']:<26} {row}  {ok}")
        print(f"{'TOTAL':<26} " + ' '.join(
            f"{sum(1 for r in rs if r['stage_b']['modes'][m]['present']):>4}"
            for m in MODES))


def trace(prefix):
    recs = [r for r in load() + load('original')
            if r['meta'].get('id', '').startswith(prefix)]
    if not recs:
        sys.exit(f'no judged trace matching {prefix!r}')
    for r in recs:
        m = r['meta']
        print(f"\n##### {m.get('era')}/{m['system']}/{m['id']}")
        print('TRACE FILE:', m.get('trace'))
        print('\n--- narrative\n' + r['stage_a'].get('narrative', ''))
        print('\n--- findings')
        for i, f in enumerate(r['stage_a'].get('findings', [])):
            tag = 'innocent?' if f.get('possibly_innocent') else 'PROBLEM'
            print(f"\n[{i}] ({tag}) {f.get('kind')} — {f.get('description')}")
            print(f"    agents: {', '.join(f.get('agents', []))}")
            print(f"    impact: {f.get('impact')}")
            print(f"    quote:  {str(f.get('evidence'))[:300]}")
        print('\n--- MAST modes')
        print('task_success:', r['stage_b'].get('task_success'),
              '|', r['stage_b'].get('summary'))
        for mode in MODES:
            v = r['stage_b']['modes'][mode]
            if v['present']:
                print(f"\n{mode} PRESENT — {v.get('note')}")
                print(f"    quote: {str(v.get('evidence'))[:300]}")


def mode(code):
    for r in load():
        v = r['stage_b']['modes'].get(code)
        if v and v['present']:
            m = r['meta']
            print(f"\n### {m['system']}/{m['id']}")
            print('note: ', v.get('note'))
            print('quote:', str(v.get('evidence'))[:400])


def kinds(system=None):
    groups = defaultdict(list)
    for r in load():
        if system and r['meta']['system'] != system:
            continue
        for f in r['stage_a'].get('findings', []):
            k = (f.get('kind') or '?').lower().strip()
            if k in ARTIFACT_KINDS:
                continue
            groups[k].append((r['meta']['id'], f.get('description', '')))
    for k, items in sorted(groups.items(), key=lambda x: -len(x[1])):
        if len(items) < 2:
            continue
        print(f"\n{k}  ({len(items)} findings in "
              f"{len({t for t, _ in items})} traces)")
        for t, d in items[:3]:
            print(f"   [{t}] {d[:130]}")


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == 'overview':
        overview()
    elif a[0] == 'trace':
        trace(a[1])
    elif a[0] == 'mode':
        mode(a[1])
    elif a[0] == 'kinds':
        kinds(a[2] if len(a) > 2 and a[1] == '--system' else
              (a[1].split('=')[1] if len(a) > 1 and '=' in a[1] else None))
    else:
        sys.exit(__doc__)
