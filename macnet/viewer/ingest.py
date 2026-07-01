#!/usr/bin/env python3
"""Ingest a MacNet arm-sweep run into macnet/traces/<arm>/<task>/ for the viewer.

Post-processes what a run already leaves behind — the per-arm total_task.log plus the
tag-attributed calls in shared/proxy/{calls,raw_calls}.jsonl — into a self-contained,
durable trace dir. Touches nothing in the harness; safe to re-run (idempotent per arm).

Each arm's calls are identified by their proxy TAG (e.g. smoke_alf8_voyager), so runs
must have been launched with a distinct MACNET_TAG per arm. Snapshotting the tagged
proxy lines here makes the trace immune to raw_calls.jsonl rotation.

Usage:
  python macnet/viewer/ingest.py <logs_dir> <tag_prefix> [--task alfworld --offset 8 \
      --max_trials 6 --title "put a hot mug in coffeemachine"]
  # <logs_dir> holds <arm>.log files; tag for arm X is "<tag_prefix><arm>".
"""
import argparse
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                          # macnet/
REPO_ROOT = os.path.dirname(ROOT)
PROXY = os.path.join(REPO_ROOT, "shared", "proxy")
TRACES = os.path.join(ROOT, "traces")

ARMS = ["vanilla", "full_memory", "memorybank", "metagpt", "voyager", "belief_state"]


def _snapshot_by_tag(src_name, tag, dest):
    """Copy only the lines of shared/proxy/<src_name> whose tag == `tag`. Substring
    prefilter (fast on the big raw_calls file), then exact JSON check."""
    src = os.path.join(PROXY, src_name)
    needle = f'"tag": "{tag}"'
    n = 0
    with open(dest, "w", encoding="utf-8") as w:
        if os.path.exists(src):
            with open(src, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if needle not in line:
                        continue
                    try:
                        if json.loads(line).get("tag") == tag:
                            w.write(line)
                            n += 1
                    except Exception:
                        pass
    return n


def ingest(logs_dir, tag_prefix, task, offset, max_trials, title):
    made = []
    for arm in ARMS:
        log = os.path.join(logs_dir, f"{arm}.log")
        if not os.path.isfile(log):
            print(f"  skip {arm}: no {log}")
            continue
        tag = f"{tag_prefix}{arm}"
        dest = os.path.join(TRACES, arm, f"{task}_off{offset}")
        os.makedirs(dest, exist_ok=True)
        shutil.copy(log, os.path.join(dest, "total_task.log"))
        n_calls = _snapshot_by_tag("calls.jsonl", tag, os.path.join(dest, "calls.jsonl"))
        n_raw = _snapshot_by_tag("raw_calls.jsonl", tag, os.path.join(dest, "raw_calls.jsonl"))
        meta = {"arm": arm, "task": task, "offset": offset, "max_trials": max_trials,
                "tag": tag, "title": title}
        with open(os.path.join(dest, "meta.json"), "w", encoding="utf-8") as w:
            json.dump(meta, w, indent=2)
        made.append((arm, n_calls, n_raw))
        print(f"  {arm:14} -> {os.path.relpath(dest, REPO_ROOT)}  ({n_calls} calls, {n_raw} raw)")
    return made


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("logs_dir")
    ap.add_argument("tag_prefix")
    ap.add_argument("--task", default="alfworld")
    ap.add_argument("--offset", type=int, default=8)
    ap.add_argument("--max_trials", type=int, default=6)
    ap.add_argument("--title", default="")
    a = ap.parse_args()
    print(f"ingesting {a.logs_dir} (tag {a.tag_prefix}*) -> {os.path.relpath(TRACES, REPO_ROOT)}")
    ingest(a.logs_dir, a.tag_prefix, a.task, a.offset, a.max_trials, a.title)
    print("done.")
