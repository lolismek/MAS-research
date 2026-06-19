#!/usr/bin/env python3
"""Build data.js for the board viewer (index.html) from the committed board runs.

Mirrors the split4_openai viewer: the main panel is the GROUP CHAT (published
messages); clicking a message opens the private trace (per-round reasoning summary +
tool loop) in a drawer, and clicking a Selector chip shows its routing reasoning. For
board runs the drawer ALSO shows the scratchpad the agent read at turn start and flags
its add_note/revise_note calls as board writes.

The timeline (with reasoning) is reconstructed from the proxy wire dump
shared/proxy/raw_calls.jsonl, keyed by tag agc_<namespace>_<uid8>_run<N> — the same
reconstruction as judging/analysis_postfix/build_inputs.py, but board-aware (the board
is injected as a 2nd system message, so the role prompt is system[0]).

Data is embedded into data.js (a <script>, not a fetch), so index.html opens straight
from disk (file://). Re-run after any new board run:  python build_board_view.py
"""
import json
import os
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))   # eval-clean repo root
TRACES = os.path.join(ROOT, "autogen_gc", "traces")
RAW = os.path.join(ROOT, "shared", "proxy", "raw_calls.jsonl")
TOOL_RESULT_CAP = 6000   # chars per tool result (full text stays in raw_calls.jsonl)


def is_selector(row):
    return "Select the SINGLE next member" in json.dumps(row.get("messages", []))


def cap(content):
    if isinstance(content, list):
        content = json.dumps(content)
    content = str(content)
    if len(content) > TOOL_RESULT_CAP:
        content = content[:TOOL_RESULT_CAP] + "\n…[truncated]"
    return content


def split_system(seg):
    """From a turn's first row, return (role_prompt, board_seen). Board mode sends two
    system messages: the role prompt ('You are …') and the injected scratchpad block
    ('=== SHARED TEAM SCRATCHPAD …'). Either may be absent."""
    role, board = "", ""
    for m in seg[0].get("messages", []):
        if m.get("role") != "system":
            continue
        c = m.get("content", "") or ""
        if "SHARED TEAM SCRATCHPAD" in c:
            board = c
        elif c.strip().startswith("You are") and not role:
            role = c
        elif not role:
            role = c   # fallback: first system message
    return role, board


def infer_source(role):
    s = (role or "").strip()
    for name in ("WebResearcher", "Analyst", "Critic", "Finalizer"):
        if s.startswith(f"You are {name}") or s.startswith(f"You are the {name}"):
            return name
    return "?"


def build_turn(seg):
    seg = sorted(seg, key=lambda r: r["ts"])
    role, board_seen = split_system(seg)
    results = {}
    for row in seg:
        for m in row.get("messages", []):
            if m.get("role") == "tool":
                results[m.get("tool_call_id")] = cap(m.get("content", ""))
    rounds = []
    for row in seg:
        reasoning = (row.get("reasoning") or "").strip()
        reply = row.get("reply", {})
        tcs = reply.get("tool_calls") if isinstance(reply, dict) else None
        if tcs:
            tools = []
            for tc in tcs:
                fn = tc.get("function", {})
                args = fn.get("arguments", "")
                try:
                    args = json.dumps(json.loads(args), indent=1)
                except Exception:
                    pass
                tools.append({"name": fn.get("name", "?"), "args": args,
                              "result": results.get(tc.get("id"))})
            rounds.append({"reasoning": reasoning, "tools": tools, "publish": None})
        else:
            content = reply.get("content", "") if isinstance(reply, dict) else str(reply)
            rounds.append({"reasoning": reasoning, "tools": [], "publish": content or ""})
    published = ""
    last_reply = seg[-1].get("reply", {})
    if isinstance(last_reply, dict):
        published = last_reply.get("content", "") or ""
    return role, board_seen, rounds, published


def build_timeline(rows):
    rows = sorted(rows, key=lambda r: r["ts"])
    timeline, i, n = [], 0, len(rows)
    pending_sel = None
    while i < n:
        r = rows[i]
        if is_selector(r):
            reply = r.get("reply", {})
            content = reply.get("content", "") if isinstance(reply, dict) else str(reply)
            lines = [ln for ln in (content or "").splitlines() if ln.strip()]
            choice = lines[-1].strip() if lines else (content or "").strip()
            pending_sel = {"choice": choice,
                           "reasoning": (r.get("reasoning") or "").strip(),
                           "rationale": "\n".join(lines[:-1]).strip() if len(lines) > 1 else "",
                           "prompt": (r["messages"][0].get("content", "") if r.get("messages") else "")}
            i += 1
            continue
        seg = []
        while i < n and not is_selector(rows[i]):
            seg.append(rows[i]); i += 1
        role, board_seen, rounds, published = build_turn(seg)
        n_writes = sum(1 for rd in rounds for t in rd["tools"]
                       if t["name"] in ("add_note", "revise_note"))
        timeline.append({"source": infer_source(role), "selector": pending_sel,
                         "system": role, "board_seen": board_seen,
                         "rounds": rounds, "published": published,
                         "n_internal_calls": len(seg), "n_writes": n_writes})
        pending_sel = None
    return timeline


def read_text(path, default=""):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return default


def read_json(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def collect(by_tag):
    runs = []
    if not os.path.isdir(TRACES):
        return runs
    for ns in sorted(os.listdir(TRACES)):
        if not ns.startswith("split4_board"):
            continue
        for uid_dir in sorted(glob.glob(os.path.join(TRACES, ns, "*"))):
            uid = os.path.basename(uid_dir)
            for run_dir in sorted(glob.glob(os.path.join(uid_dir, "run_*")),
                                  key=lambda p: int(p.rsplit("_", 1)[1])):
                if not os.path.isfile(os.path.join(run_dir, "board_trace.jsonl")):
                    continue
                runN = int(run_dir.rsplit("_", 1)[1])
                tag = f"agc_{ns}_{uid}_run{runN}"
                rows = by_tag.get(tag, [])
                timeline = build_timeline(rows) if rows else []
                res = read_json(os.path.join(run_dir, "result.json"))
                runs.append({
                    "namespace": ns, "uuid": uid, "run": run_dir.rsplit("/", 1)[-1],
                    "label": f"{ns}/{uid}/run{runN}",
                    "tag": tag, "no_data": not rows,
                    "prompt": read_text(os.path.join(run_dir, "prompt.txt")),
                    "expected": read_text(os.path.join(run_dir, "expected_answer.txt")),
                    "result": {k: res.get(k) for k in (
                        "final_answer", "exact_match", "board_event_count",
                        "board_note_count", "board_revise_count", "board_authors")},
                    "timeline": timeline,
                })
    runs.sort(key=lambda r: (r["namespace"], r["uuid"], r["run"]))
    return runs


def main():
    by_tag = {}
    if os.path.isfile(RAW):
        with open(RAW, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                by_tag.setdefault(r.get("tag", ""), []).append(r)
    runs = collect(by_tag)
    out = os.path.join(HERE, "data.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write("window.BOARD_DATA = ")
        json.dump({"runs": runs}, f, ensure_ascii=False)
        f.write(";\n")
    print(f"wrote {out}  ({len(runs)} run(s))")
    for r in runs:
        nturns = len(r["timeline"])
        nreason = sum(1 for t in r["timeline"] for rd in t["rounds"] if rd["reasoning"]) \
            + sum(1 for t in r["timeline"] if t["selector"] and t["selector"]["reasoning"])
        flag = "  <-- NO PROXY ROWS (only console available)" if r["no_data"] else ""
        print(f"  - {r['label']:42} turns={nturns:>2} reasoning={nreason:>3} "
              f"match={r['result'].get('exact_match')}{flag}")


if __name__ == "__main__":
    main()
