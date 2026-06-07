"""Build the stratified, original-FAILED GAIA seed set -> results/tasks.jsonl.

Join: each MAD Magentic label record's `trajectory` is the full console log, so we
match it to a local GAIA task by checking whether that task's prompt.txt appears
(whitespace-normalized) as a substring of the trajectory. Then keep only tasks the
original Magentic-One run FAILED, and stratify to N_TASKS by failure mode + level.

No API calls. Run: python eval/select_tasks.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
from grade import grade, extract_final_answer

WS = re.compile(r"\s+")
def norm(s: str) -> str:
    return WS.sub(" ", s.strip().lower())


# ---- modality filter: drop tasks that need audio/video we can't access ----
# (Perplexity has no audio/vision; markitdown can't transcribe audio.) These would
# fail for a MODALITY reason, not inter-agent misalignment, so they're excluded so
# the structural-vs-capability signal isn't muddied. Visual tasks whose answer
# lives in TEXT (PDF/HTML/page explanations) are intentionally kept.
AV_EXT = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac",
          ".mp4", ".mov", ".avi", ".mkv", ".webm"}
AUDIO_KW = re.compile(r"voice memo|listen to the|audio recording|\.mp3|\.wav", re.I)
VIDEO_WATCH_KW = re.compile(r"\b360\b|VR video|shown in the video|watch the video|"
                            r"frame of the video", re.I)


def modality_blocked(task):
    """Return a reason string if the task needs inaccessible audio/video, else None."""
    d = C.GAIA_LEVEL_DIRS.get(task["level"])
    if d:
        for f in (d / task["uuid"] / "0").glob(task["uuid"] + ".*"):
            if f.suffix.lower() in AV_EXT:
                return f"av-attachment({f.suffix})"
    if AUDIO_KW.search(task["prompt"]):
        return "audio-prompt"
    if VIDEO_WATCH_KW.search(task["prompt"]):
        return "video-watch-prompt"
    return None


def load_local_tasks():
    tasks = []
    for level, d in C.GAIA_LEVEL_DIRS.items():
        if not d.exists():
            continue
        for uuid_dir in sorted(d.iterdir()):
            base = uuid_dir / "0"
            p, e, c = base / "prompt.txt", base / "expected_answer.txt", base / "console_log.txt"
            if not (p.exists() and e.exists() and c.exists()):
                continue
            prompt = p.read_text(errors="ignore").strip()
            tasks.append({
                "uuid": uuid_dir.name, "level": level,
                "prompt": prompt, "prompt_norm": norm(prompt),
                "expected_answer": e.read_text(errors="ignore").strip(),
                "console_log": c,
            })
    return tasks


def load_magentic_labels():
    recs = []
    for line in open(C.CAT2_JSONL):
        r = json.loads(line)
        if r["mas_name"] == "Magentic":
            recs.append(r)
    return recs


def join(local, labels):
    """Attach cat2 labels to local tasks via prompt-in-trajectory substring match."""
    by_uuid = {}
    unmatched = 0
    for r in labels:
        traj = norm(r["trajectory"])
        # longest prompts first to avoid a short prompt matching the wrong task
        cand = sorted(local, key=lambda t: -len(t["prompt_norm"]))
        hit = next((t for t in cand if t["prompt_norm"] and t["prompt_norm"] in traj), None)
        if hit is None:
            unmatched += 1
            continue
        u = hit["uuid"]
        if u not in by_uuid:
            by_uuid[u] = {**hit, "cat2_modes": set(), "all_flags": set()}
        by_uuid[u]["cat2_modes"].update(r["cat2_modes"])
        by_uuid[u]["all_flags"].update(r["all_flags"])
    return by_uuid, unmatched


def mode_rank(modes):
    if "2.4" in modes or "2.5" in modes:
        return 0          # structural core (target) -- highest priority
    if "2.6" in modes:
        return 1          # capability control
    if "2.2" in modes or "2.3" in modes:
        return 2          # mixed
    return 3


def stratify(failed):
    """Force-include all 2.4/2.5, then fill PER-LEVEL targets (L3 first so its
    reserved slots aren't starved by the common 2.6 tasks), then top up to N."""
    want = dict(C.LEVEL_MIX)                 # {1:6, 2:6, 3:3}
    selected, sel_ids, got = [], set(), {1: 0, 2: 0, 3: 0}

    def take(t):
        if t["uuid"] in sel_ids or len(selected) >= C.N_TASKS:
            return
        if t["level"] == 3 and got[3] >= C.MAX_L3:
            return
        selected.append(t); sel_ids.add(t["uuid"]); got[t["level"]] += 1

    by_rank = lambda ts: sorted(ts, key=lambda t: mode_rank(t["cat2_modes"]))

    # 1) force structural-core (rare; respects L3 cap)
    for t in by_rank([t for t in failed if mode_rank(t["cat2_modes"]) == 0]):
        take(t)
    # 2) per-level targets, L3 first to protect its reserved slots
    for lvl in (3, 1, 2):
        for t in by_rank([t for t in failed if t["level"] == lvl]):
            if got[lvl] >= want[lvl]:
                break
            take(t)
    # 3) top up to N from whatever remains (by priority)
    for t in by_rank(failed):
        if len(selected) >= C.N_TASKS:
            break
        take(t)
    return selected


def main():
    local = load_local_tasks()
    labels = load_magentic_labels()
    print(f"local GAIA tasks: {len(local)} | Magentic label records: {len(labels)}")

    joined, unmatched = join(local, labels)
    print(f"joined (matched to a local task): {len(joined)} | unmatched labels: {unmatched}")

    # original pass/fail
    failed = []
    for t in joined.values():
        log = t["console_log"].read_text(errors="ignore")
        fa = extract_final_answer(log)
        passed = grade(fa, t["expected_answer"])
        t["orig_final_answer"] = fa
        t["orig_passed"] = passed
        if not passed:
            failed.append(t)
    from collections import Counter  # noqa
    print(f"matched & ORIGINAL-FAILED: {len(failed)} | pool by level:",
          dict(Counter(t['level'] for t in failed)))

    # drop modality-blocked (audio/video) tasks from the pool before stratifying
    blocked = [(t["uuid"][:8], modality_blocked(t)) for t in failed if modality_blocked(t)]
    failed = [t for t in failed if not modality_blocked(t)]
    print(f"excluded {len(blocked)} modality-blocked tasks: {blocked}")
    print(f"text-solvable pool: {len(failed)} | by level:",
          dict(Counter(t['level'] for t in failed)))

    sel = stratify(failed)
    print(f"\nselected {len(sel)} tasks")
    from collections import Counter  # noqa
    print("  by level:", dict(Counter(t['level'] for t in sel)))
    mc = Counter()
    for t in sel:
        for m in C.CAT2:
            if m in t["cat2_modes"]:
                mc[m] += 1
    print("  cat2 mode coverage:", dict(sorted(mc.items())))

    C.RESULTS.mkdir(exist_ok=True)
    with open(C.TASKS_JSONL, "w") as f:
        for t in sel:
            f.write(json.dumps({
                "uuid": t["uuid"], "level": t["level"], "prompt": t["prompt"],
                "expected_answer": t["expected_answer"],
                "orig_cat2_modes": sorted(t["cat2_modes"]),
                "orig_all_flags": sorted(t["all_flags"]),
                "orig_final_answer": t["orig_final_answer"],
                "orig_passed": t["orig_passed"],
            }) + "\n")
    print(f"\nwrote {C.TASKS_JSONL}")


if __name__ == "__main__":
    main()
