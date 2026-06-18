"""Merge the split4_openai per-trace input bundles (timeline WITH reasoning
summaries) + the subagent verdicts into one traces.json for the openai viewer.

Inputs:
  ../autogen_gc/analysis_postfix/inputs/<uid8>.json   (timeline: rounds w/ reasoning)
  ../autogen_gc/analysis_postfix/verdicts/<uid8>.json (per-trace verdict)
Output:
  ./traces.json   (consumed by index.html)
"""
import json, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))   # the autogen_gc/ MAS dir
ANA = os.path.join(ROOT, 'judging', 'analysis_postfix')
INP = os.path.join(ANA, 'inputs')
VER = os.path.join(ANA, 'verdicts')


def main():
    traces = []
    for f in sorted(glob.glob(os.path.join(INP, '*.json'))):
        b = json.load(open(f))
        uid8 = b['uid8']
        vf = os.path.join(VER, f'{uid8}.json')
        verdict = json.load(open(vf)) if os.path.exists(vf) else {}
        traces.append({
            'uid8': uid8, 'uuid': b.get('uuid'),
            'category': b.get('category'), 'level': b.get('level'),
            'question': b.get('question'),
            'expected_answer': b.get('expected_answer'),
            'final_answer': b.get('final_answer'),
            'exact_match': b.get('exact_match'),
            'seconds': b.get('seconds'), 'rc': b.get('rc'),
            'no_data': b.get('no_data', False),
            'participation': b.get('participation', {}),
            'verdict': verdict,
            'timeline': b.get('timeline', []),
        })

    # order: most interesting first — strong/moderate misalignment, then weak,
    # then wrong answers, then no_answer, then correct, then infra.
    order_m = {'strong': 0, 'moderate': 1, 'weak': 2, 'none': 3}
    order_o = {'wrong_answer': 0, 'no_answer': 1, 'correct': 2, 'infra_failure': 3}
    traces.sort(key=lambda t: (order_m.get(t['verdict'].get('genuine_misalignment'), 9),
                               order_o.get(t['verdict'].get('outcome'), 9), t['uid8']))

    out = os.path.join(HERE, 'traces.json')
    json.dump(traces, open(out, 'w'), indent=1)
    size = os.path.getsize(out)
    print(f'wrote {out}  ({len(traces)} traces, {size/1024:.0f} KB)')

    from collections import Counter
    print('outcome     :', dict(Counter(t['verdict'].get('outcome') for t in traces)))
    print('misalignment:', dict(Counter(t['verdict'].get('genuine_misalignment') for t in traces)))
    print('failure_cat :', dict(Counter(t['verdict'].get('failure_category') for t in traces)))
    nr = sum(1 for t in traces for tn in t['timeline'] for rd in tn['rounds'] if rd['reasoning'])
    print(f'reasoning summaries embedded: {nr}')


if __name__ == '__main__':
    main()
