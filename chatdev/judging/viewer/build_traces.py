"""Parse the ChatDev WareHouse dialogue logs into one traces.json for the viewer.

ChatDev is a waterfall of role-played *phases* over a shared code store. Each
run's `.log` is already markdown with explicit speakers and phase/turn headers:

    [ts INFO] <Speaker>: **<A><->B on : <Phase>, turn N**
    [ts INFO] <Speaker>: **[Start Chat]**
    [ts INFO] System:    **[chatting]**        <- phase-setup param table

We split on those header lines, fold the repeated role-context block that leads
every body, and tokenize each message into ordered md / code parts (code carries
a best-effort filename so the viewer can diff a file across turns).

Inputs (per task):
  ../../traces/<Task>/run_N/result.json
  ../../traces/<Task>/run_N/warehouse/<Task>_..._<ts>.log
  ../../traces/<Task>/run_N/warehouse/<product files>
  ../relational/verdicts/<Task>.md
Output:
  ./traces.json   (consumed by index.html)
"""
import json, os, re, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # the chatdev/ MAS dir
TRACES = os.path.join(ROOT, 'traces')
VERDICTS = os.path.join(ROOT, 'judging', 'relational', 'verdicts')

# header line: [2026-18-06 05:54:49 INFO] <Speaker>: **<header>**
HEADER = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \w+\] '
                    r'([^:]+?): \*\*(.*?)\*\*\s*$')
# dialogue header inside the **...**: "<A><->B on : <Phase>, turn N"
TURN = re.compile(r'^(.+?)<->(.+?) on : (.+?), turn (\d+)$')
NOISE = 'flask app.py did not start for online log'

ROLE_ABBR = {
    'Chief Executive Officer': 'CEO', 'Chief Product Officer': 'CPO',
    'Chief Technology Officer': 'CTO', 'Chief Human Resource Officer': 'CHRO',
    'Programmer': 'PRG', 'Code Reviewer': 'REV',
    'Software Test Engineer': 'TST', 'Counselor': 'CNS', 'System': 'SYS',
}

FILE_RE = re.compile(r'([\w./-]+\.(?:py|md|txt|html|css|js|json|cfg|sh))')


def split_entries(text):
    """Flat list of {ts, speaker, header, body} split on header lines."""
    entries, cur = [], None
    for line in text.splitlines():
        m = HEADER.match(line)
        if m:
            if cur:
                entries.append(cur)
            cur = {'ts': m.group(1), 'speaker': m.group(2).strip(),
                   'header': m.group(3).strip(), 'body': []}
        elif cur is not None:
            if NOISE in line:
                continue
            cur['body'].append(line)
    if cur:
        entries.append(cur)
    return entries


def fold_context(lines):
    """Strip the leading [ChatDev is a software company ...] role-context block.

    Returns (context_str_or_None, remaining_lines).
    """
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith('[ChatDev is a software company'):
        ctx = []
        while i < len(lines):
            ctx.append(lines[i])
            if lines[i].rstrip().endswith(']'):
                i += 1
                break
            i += 1
        return '\n'.join(ctx).strip(), lines[i:]
    return None, lines


def tokenize(lines):
    """Body lines -> ordered parts: {t:'md',text} | {t:'code',filename,lang,code}.

    Filename for a code part = nearest filename-looking token in the md above it.
    """
    parts, buf, last_file = [], [], None

    def flush_md():
        nonlocal last_file
        if not buf:
            return
        txt = '\n'.join(buf).strip('\n')
        if txt.strip():
            parts.append({'t': 'md', 'text': txt})
            # remember the last filename mentioned, for the next code fence
            for ln in reversed(buf):
                m = FILE_RE.search(ln)
                if m and len(ln.strip()) < 80:   # a heading/label, not prose
                    last_file = m.group(1)
                    break
        buf.clear()

    i, n = 0, len(lines)
    while i < n:
        fence = re.match(r'^\s*```(\w+)?\s*$', lines[i])
        if fence:
            flush_md()
            lang = fence.group(1) or ''
            i += 1
            code = []
            while i < n and not re.match(r'^\s*```\s*$', lines[i]):
                code.append(lines[i])
                i += 1
            i += 1  # closing fence
            parts.append({'t': 'code', 'filename': last_file, 'lang': lang,
                          'code': '\n'.join(code)})
            last_file = None
        else:
            buf.append(lines[i])
            i += 1
    flush_md()
    return parts


def parse_log(text):
    """-> (segments, task_prompt, software_info)."""
    task_prompt = ''
    mtp = re.search(r'\*\*task_prompt\*\*:\s*(.+)', text)
    if mtp:
        task_prompt = mtp.group(1).strip()

    software = {}
    for k, v in re.findall(r'\*\*(\w+)\*\*=(\S+)', text):
        if k in ('cost', 'code_lines', 'num_utterances', 'num_self_reflections',
                 'num_total_tokens', 'version_updates', 'num_code_files',
                 'num_doc_files', 'duration'):
            software[k] = v

    segments, seg = [], None
    for e in split_entries(text):
        sp, hd = e['speaker'], e['header']
        if sp == 'System':
            if hd == '[chatting]':
                body = '\n'.join(e['body'])
                pn = re.search(r'\*\*phase_name\*\*\s*\|\s*(.+?)\s*\|', body)
                ar = re.search(r'\*\*assistant_role_name\*\*\s*\|\s*(.+?)\s*\|', body)
                ur = re.search(r'\*\*user_role_name\*\*\s*\|\s*(.+?)\s*\|', body)
                seg = {'phase': pn.group(1) if pn else '?',
                       'roles': [ar.group(1) if ar else '', ur.group(1) if ur else ''],
                       'messages': []}
                segments.append(seg)
            continue  # skip RolePlaying / Preprocessing / Software Info tables
        if seg is None:
            continue
        ctx, rest = fold_context(e['body'])
        parts = tokenize(rest)
        if not parts and not ctx:
            continue
        tm = TURN.match(hd)
        msg = {'speaker': sp, 'abbr': ROLE_ABBR.get(sp, sp[:3].upper()),
               'kind': 'start' if hd == '[Start Chat]' else 'turn',
               'turn': int(tm.group(4)) if tm else None,
               'context': ctx, 'parts': parts}
        seg['messages'].append(msg)
    return segments, task_prompt, software


def collect_files(warehouse):
    skip_suffix = ('.log', '.prompt')
    skip_name = {'meta.txt', 'ChatChainConfig.json', 'PhaseConfig.json',
                 'RoleConfig.json'}
    out = []
    for fn in sorted(os.listdir(warehouse)):
        p = os.path.join(warehouse, fn)
        if not os.path.isfile(p) or fn in skip_name or fn.endswith(skip_suffix):
            continue
        lang = {'py': 'python', 'md': 'markdown', 'js': 'javascript',
                'html': 'html', 'css': 'css'}.get(fn.rsplit('.', 1)[-1], '')
        try:
            out.append({'name': fn, 'lang': lang,
                        'content': open(p, encoding='utf-8', errors='replace').read()})
        except OSError:
            pass
    return out


def parse_verdict(task):
    p = os.path.join(VERDICTS, f'{task}.md')
    if not os.path.exists(p):
        return {}
    md = open(p, encoding='utf-8').read()
    title = re.search(r'^##\s+TRACE\s+.+?—\s+(.+?)\s+—\s+misalignment:\s+(\w+)',
                      md, re.M)
    outcome = re.search(r'\*\*Outcome:\*\*\s*\*?\*?(.+?)[.\n]', md)
    return {
        'summary': title.group(1).strip() if title else '',
        'misalignment': title.group(2).strip().lower() if title else 'n/a',
        'outcome': (outcome.group(1).strip().rstrip('*') if outcome else ''),
        'md': md,
    }


def main():
    traces = []
    for task_dir in sorted(glob.glob(os.path.join(TRACES, '*'))):
        task = os.path.basename(task_dir)
        if task == 'original_gpt4o' or not os.path.isdir(task_dir):
            continue
        for run_dir in sorted(glob.glob(os.path.join(task_dir, 'run_*'))):
            warehouse = os.path.join(run_dir, 'warehouse')
            logs = glob.glob(os.path.join(warehouse, '*.log'))
            if not logs:
                continue
            text = open(logs[0], encoding='utf-8', errors='replace').read()
            result = {}
            rp = os.path.join(run_dir, 'result.json')
            if os.path.exists(rp):
                result = json.load(open(rp))
            segments, task_prompt, software = parse_log(text)
            traces.append({
                'task': task,
                'run': os.path.basename(run_dir),
                'rc': result.get('rc'),
                'seconds': result.get('seconds'),
                'original_solved': result.get('original_solved'),
                'cat2': result.get('cat2_likelihood_screened'),
                'task_prompt': task_prompt,
                'software_info': software,
                'verdict': parse_verdict(task),
                'segments': segments,
                'files': collect_files(warehouse),
            })

    order_m = {'strong': 0, 'moderate': 1, 'weak': 2, 'none': 3, 'n/a': 9}
    traces.sort(key=lambda t: (order_m.get(t['verdict'].get('misalignment'), 9),
                               t['task']))

    out = os.path.join(HERE, 'traces.json')
    json.dump(traces, open(out, 'w'), indent=1)
    size = os.path.getsize(out)
    print(f'wrote {out}  ({len(traces)} traces, {size/1024:.0f} KB)')
    from collections import Counter
    print('misalignment:', dict(Counter(t['verdict'].get('misalignment') for t in traces)))
    nmsg = sum(len(s['messages']) for t in traces for s in t['segments'])
    ncode = sum(1 for t in traces for s in t['segments'] for m in s['messages']
                for p in m['parts'] if p['t'] == 'code')
    print(f'segments: {sum(len(t["segments"]) for t in traces)}, '
          f'messages: {nmsg}, code-parts: {ncode}')


if __name__ == '__main__':
    main()
