"""Deeper cuts on the internal-belief batch: early-finish split, edge-1 carry vs accuracy, interpretation-lost with the all-arm as control, per-type, task-level majorities. Run from repo root."""
import json, glob, collections, sys, os
sys.path.insert(0, 'lip/internal'); from summarize import carries
tasks = {json.loads(l)['id']: json.loads(l) for l in open('lip/data/tasks_internal.jsonl')}
R = {}
for arm in ['internal_none', 'internal_first', 'internal_all']:
    for p in glob.glob(f'lip/traces/{arm}/*/run_*/run.json'):
        r = json.load(open(p)); a1 = r['agents'][0] if r['agents'] else {}
        R.setdefault(arm, []).append(dict(id=r['task_id'], run=r['run'], ok=bool(r['correct']), fb=r.get('finished_by'),
            final=(r['final'] or '').strip().lower(), h1=a1.get('handoff') or '', opened1=len(a1.get('opened') or []),
            carry=carries(a1.get('handoff') or '', tasks[r['task_id']]['qualifier']), typ=tasks[r['task_id']]['qualifier_type']))
def acc(rs): return f"{sum(x['ok'] for x in rs)}/{len(rs)} = {sum(x['ok'] for x in rs)/max(1,len(rs)):.3f}"
print("A. split by agent-1 finish")
for arm, rs in R.items():
    f1 = [x for x in rs if x['fb'] == 1]; ho = [x for x in rs if x['fb'] != 1]
    print(f"  {arm:15s} a1-finished {acc(f1):18s} handed-off {acc(ho)}   a1 opened pages when finishing: {sum(x['opened1']>0 for x in f1)}/{len(f1)}")
print("B. handed-off runs: accuracy by whether agent-1 handoff carries the qualifier")
for arm, rs in R.items():
    ho = [x for x in rs if x['fb'] != 1]
    print(f"  {arm:15s} carries {acc([x for x in ho if x['carry']]):18s} drops {acc([x for x in ho if not x['carry']])}")
print("C. interpretation-lost: failures whose final == modal none-arm final (control = same stat in the all arm)")
modal = {}
for t in tasks:
    fs = [x['final'] for x in R['internal_none'] if x['id'] == t and x['final']]
    modal[t] = collections.Counter(fs).most_common(1)[0][0] if fs else None
for arm in ['internal_first', 'internal_all']:
    fails = [x for x in R[arm] if not x['ok']]
    lost = [x for x in fails if modal.get(x['id']) and x['final'] == modal[x['id']]]
    lost_ho = [x for x in lost if x['fb'] != 1]; lost_drop = [x for x in lost_ho if not x['carry']]
    print(f"  {arm:15s} failures {len(fails)}, match modal-none {len(lost)} ({len(lost_ho)} handed off, of which {len(lost_drop)} dropped qualifier at edge 1)")
print("D. accuracy by qualifier type")
for typ in ['temporal', 'scope', 'entity', 'unit', 'other']:
    print(f"  {typ:9s}", "  ".join(f"{arm[9:]} {acc([x for x in rs if x['typ']==typ])}" for arm, rs in R.items()))
print("E. task-level majority (>=2/3 correct)")
maj = {arm: {t: sum(x['ok'] for x in rs if x['id']==t) >= 2 for t in tasks} for arm, rs in R.items()}
n, f, a = maj['internal_none'], maj['internal_first'], maj['internal_all']
print(f"  majority-correct: none {sum(n.values())}, first {sum(f.values())}, all {sum(a.values())}")
print(f"  all yes & first no: {sum(a[t] and not f[t] for t in tasks)}  (of which none no: {sum(a[t] and not f[t] and not n[t] for t in tasks)})")
print(f"  first yes & none no: {sum(f[t] and not n[t] for t in tasks)}   all yes & none no: {sum(a[t] and not n[t] for t in tasks)}   first yes & all no: {sum(f[t] and not a[t] for t in tasks)}")
print("  internal-loss candidates (all yes, first no, none no):")
for t in tasks:
    if a[t] and not f[t] and not n[t]:
        fin = lambda arm: [x['final'][:25] for x in sorted(R[arm], key=lambda x: x['run']) if x['id']==t]
        print(f"   {t} [{tasks[t]['qualifier_type']}] q='{tasks[t]['qualifier'][:40]}' gold='{tasks[t]['answer'][:25]}'\n      none {fin('internal_none')}\n      first {fin('internal_first')}  carry={[x['carry'] for x in sorted(R['internal_first'], key=lambda x: x['run']) if x['id']==t]}\n      all {fin('internal_all')}")
