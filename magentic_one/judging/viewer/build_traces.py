"""Build traces.json for the Magentic-One trace viewer.

Magentic-One is hub-and-spoke: a MagenticOneOrchestrator (the hub) plans a Task
Ledger, then routes instructions to specialist spokes (WebSurfer, Assistant,
FileSurfer, ComputerTerminal) and self-grades. Unlike the AutoGen GroupChat
viewer there is no Selector agent and no private ReAct/reasoning layer in these
runs — the committed console transcript is the public record, so the timeline is
simply the ordered sequence of messages.

Inputs (all under ../.. = the magentic_one/ MAS dir):
  tasks/magentic_gaia_tasks.json        (question, level, expected per uuid)
  judging/results_13tasks.json          (final/expected/exact_match/seconds/rc/run)
  judging/FAILURE_ANALYSIS_verdicts.md  (per-trace verdict prose, by uid8)
  traces/<uid8>/run_<run>/console_log.txt   (the transcript to replay)

Output:
  ./traces.json   (consumed by index.html)
"""
import json, os, re, glob

HERE = os.path.dirname(os.path.abspath(__file__))
MAS = os.path.dirname(os.path.dirname(HERE))          # the magentic_one/ dir
TASKS = os.path.join(MAS, 'tasks', 'magentic_gaia_tasks.json')
RESULTS = os.path.join(MAS, 'judging', 'results_13tasks.json')
VERDICTS = os.path.join(MAS, 'judging', 'FAILURE_ANALYSIS_verdicts.md')
TRACES = os.path.join(MAS, 'traces')

MSG_RE = re.compile(r'^-{6,}\s*(.+?)\s*-{6,}\s*$')
BACKEND_RE = re.compile(r'(\[(?:search-backend|de-bing)\][^\n]*)')
HUB = 'MagenticOneOrchestrator'


# ---------------------------------------------------------------- console parse
def parse_console(path):
    """Split an AutoGen console log into ordered messages, dropping the preamble
    (warnings / backend banner) before the first '---------- user ----------'."""
    backend = None
    msgs, src, buf = [], None, []

    def flush():
        if src is not None:
            text = '\n'.join(buf).strip('\n').rstrip()
            msgs.append({'source': src, 'text': text})

    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.rstrip('\n')
        if backend is None:
            m = BACKEND_RE.search(line)
            if m:
                backend = m.group(1)
        m = MSG_RE.match(line)
        if m:
            flush()
            src, buf = m.group(1), []
        elif src is not None:
            buf.append(line)
    flush()
    return msgs, backend


def first_line(text, n=300):
    for ln in text.split('\n'):
        ln = ln.strip()
        if ln:
            return (ln[:n] + '…') if len(ln) > n else ln
    return ''


def build_timeline(msgs):
    """Tag each message with role (user/hub/spoke) and kind. The first hub
    message is the Task Ledger; a hub message starting 'FINAL ANSWER' is the
    finalization; other hub messages are routing instructions to a spoke."""
    timeline, seen_ledger = [], False
    counts = {}
    for i, m in enumerate(msgs):
        src, text = m['source'], m['text']
        counts[src] = counts.get(src, 0) + 1
        if src == 'user':
            role, kind = 'user', 'task'
        elif src == HUB:
            role = 'hub'
            if not seen_ledger:
                kind, seen_ledger = 'ledger', True
            elif text.lstrip().upper().startswith('FINAL ANSWER'):
                kind = 'final'
            else:
                kind = 'instruction'
        else:
            role, kind = 'spoke', 'normal'
        timeline.append({
            'i': i, 'source': src, 'role': role, 'kind': kind,
            'preview': first_line(text), 'text': text, 'chars': len(text),
        })
    return timeline, counts


# ---------------------------------------------------------------- verdict parse
def parse_verdicts(path):
    """Parse the markdown verdict appendix into {uid8: {...}} preserving the
    in-document block order (a deliberate pedagogical ordering)."""
    txt = open(path, encoding='utf-8').read()
    blocks = re.split(r'\n(?=## TRACE )', txt)
    out, order = {}, {}
    head_re = re.compile(r'## TRACE (\w+) \(([^)]*)\)\s*—\s*(.+)')
    # label sits inside the bold span; the colon may be inside it (**Outcome:**)
    # or absent when the label ends in '?' (**Genuine misalignment?**).
    bullet_re = re.compile(r'^- \*\*(.+?)\*\*:?\s?(.*)$')
    n = 0
    for b in blocks:
        hm = head_re.search(b)
        if not hm:
            continue
        uid8, lvl, headline = hm.group(1), hm.group(2), hm.group(3).strip()
        fields, cur = [], None
        for line in b.splitlines()[1:]:
            if line.strip() == '---':
                break
            bm = bullet_re.match(line)
            if bm:
                cur = {'label': bm.group(1).rstrip(':').strip(), 'text': bm.group(2).strip()}
                fields.append(cur)
            elif cur is not None and line.strip():
                cur['text'] += '\n' + line.strip()
        fmap = {f['label'].lower(): f['text'] for f in fields}
        mis_txt = next((v for k, v in fmap.items() if 'misalign' in k), '') or ''
        mu = mis_txt.upper()
        if 'PARTIAL' in mu or mu.startswith('YES'):
            misalign = 'partial'
        elif 'BORDERLINE' in mu:
            misalign = 'borderline'
        else:
            misalign = 'none'
        hl = headline.lower()
        substantive = any(s in hl for s in (
            'substantively correct', 'substantively right', 'grading artifact',
            'harness artifact', 'success'))
        # Don't surface codes the prose explicitly negates: 'none. Notably
        # avoided 1.3 …' (clean traces) or '… Not 2.4/2.5' (3cef3a44). Cut the
        # text only at a negation word directly followed by a code, so a stray
        # 'lets it not affect the result' before real codes is left intact.
        mast_txt = fmap.get('mast', '')
        if re.match(r'\s*none', mast_txt, re.I):
            mast_codes = []
        else:
            neg = re.search(r'\b(?:not|notably(?:\s+avoided)?|incipient|avoided)\b\W*\d\.\d',
                            mast_txt, re.I)
            core = mast_txt[:neg.start()] if neg else mast_txt
            mast_codes = sorted(set(re.findall(r'\b\d\.\d\b', core)))
        out[uid8] = {
            'headline': headline, 'level_label': lvl, 'fields': fields,
            'misalign': misalign, 'substantive': substantive,
            'mast_codes': mast_codes, 'misalign_text': mis_txt,
        }
        order[uid8] = n
        n += 1
    return out, order


# ---------------------------------------------------------------- assemble
def main():
    tasks = {t['uuid']: t for t in json.load(open(TASKS))}
    results = json.load(open(RESULTS))
    verdicts, order = parse_verdicts(VERDICTS)

    traces = []
    for r in results:
        uuid = r['uuid']
        uid8 = uuid[:8]
        run = r.get('run', 1)
        task = tasks.get(uuid, {})
        v = verdicts.get(uid8, {})

        log = os.path.join(TRACES, uid8, f'run_{run}', 'console_log.txt')
        if not os.path.exists(log):  # fall back to whatever run dir exists
            cand = sorted(glob.glob(os.path.join(TRACES, uid8, 'run_*', 'console_log.txt')))
            log = cand[-1] if cand else None
        timeline, counts, backend, no_data = [], {}, None, True
        if log:
            msgs, backend = parse_console(log)
            if any(m['source'] == 'user' for m in msgs):
                timeline, counts = build_timeline(msgs)
                no_data = False

        final = r.get('final_answer')
        outcome = ('correct' if r.get('exact_match')
                   else 'no_answer' if final in (None, '') else 'wrong_answer')

        traces.append({
            'uid8': uid8, 'uuid': uuid, 'run': run,
            'level': r.get('level') or task.get('level'),
            'task_type': 'web' if counts.get('WebSurfer') else 'reasoning',
            'question': task.get('question', ''),
            'expected_answer': r.get('expected_answer'),
            'final_answer': final,
            'exact_match': r.get('exact_match'),
            'seconds': r.get('seconds'), 'rc': r.get('rc'),
            'backend': backend, 'no_data': no_data,
            'outcome': outcome,
            'substantive': v.get('substantive', False),
            'misalign': v.get('misalign', 'none'),
            'mast_codes': v.get('mast_codes', []),
            'counts': counts,
            'verdict': {'headline': v.get('headline'), 'fields': v.get('fields', [])},
            'timeline': timeline,
        })

    # preserve the verdict-doc ordering (success control → artifacts → wrong)
    traces.sort(key=lambda t: (order.get(t['uid8'], 99), t['uid8']))

    out = os.path.join(HERE, 'traces.json')
    json.dump(traces, open(out, 'w'), ensure_ascii=False, indent=1)
    from collections import Counter
    print(f'wrote {out}  ({len(traces)} traces, {os.path.getsize(out)/1024:.0f} KB)')
    print('outcome    :', dict(Counter(t['outcome'] for t in traces)))
    print('substantive:', sum(t['substantive'] for t in traces))
    print('misalign   :', dict(Counter(t['misalign'] for t in traces)))
    print('no_data    :', [t['uid8'] for t in traces if t['no_data']])
    print('msgs total :', sum(len(t['timeline']) for t in traces))


if __name__ == '__main__':
    main()
