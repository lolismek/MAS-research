"""GAIA level-3 -> tasks.jsonl (the project's flagship: hardest multi-step tool-use).

Pulls the REAL gaia-benchmark/GAIA validation split (the one with gold answers; the
test split is answer-blind) and keeps level-3 — GAIA's hard slice (long multi-source
tool chains), which is what justifies the multi-agent machinery.

Our backend (Qwen3.6-35B-A3B) is TEXT-ONLY and our tools are text/web/compute, so we
split the 26 L3 tasks by what they actually require:

  * EVALUATED (-> tasks.jsonl): solvable with text tools. Document attachments
    (xlsx/csv/zip/jsonld) are staged into files/ and read via the read_file tool;
    PDF-on-the-web tasks are handled by fetch_url's PDF extraction.
  * EXCLUDED (-> excluded_vision.jsonl): need vision/video/audio — an image/chart/map
    the human reference solution used "image recognition / computer vision / video /
    audio" tools for, OR an image attachment. NOT evaluated (would be guaranteed
    failures + honesty-axis noise). Kept on disk so a future vision-capable model can
    pick them up; a committable, paraphrased index lives in EXCLUDED.md.

GAIA is GATED: needs HUGGINGFACE_TOKEN (.env) + a one-time access grant on
https://huggingface.co/datasets/gaia-benchmark/GAIA . Prep also needs pyarrow (parquet)
and downloads doc attachments into files/ (git-ignored, like tasks.jsonl).

Run: conda run -n autogen_gc python benchmarks/gaia/prep.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import REPO_ROOT, hf_token, write_tasks  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(HERE, "files")

# A task is modality-gated (un-evaluable on a text-only model) if the human reference
# solution used one of these tool families, OR if its attachment is image/audio/video.
_MODALITY_KW = ["image recognition", "computer vision", "image processing",
                "video recognition", "video capability", "audio capability",
                "ocr", "speech recognition", "object detection"]
_MEDIA_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg",
              ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".mp4", ".mov", ".avi", ".mkv"}


def _modality_reason(question_tools, ext):
    """Return a short reason string if the task needs vision/audio/video, else ''."""
    tl = (question_tools or "").lower()
    hit = next((k for k in _MODALITY_KW if k in tl), None)
    if hit:
        return f"ref solution used '{hit}'"
    if ext in _MEDIA_EXT:
        return f"media attachment ({ext})"
    return ""


def build():
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq
    path = hf_hub_download("gaia-benchmark/GAIA", "2023/validation/metadata.level3.parquet",
                           repo_type="dataset", token=hf_token())
    rows = pq.read_table(path).to_pylist()

    os.makedirs(FILES_DIR, exist_ok=True)
    evaluated, excluded = [], []
    for r in rows:
        fname = (r.get("file_name") or "").strip()
        ext = os.path.splitext(fname)[1].lower()
        ann = r.get("Annotator Metadata") or {}
        rec = dict(
            id=f"gaia_{r['task_id'][:8]}", bench="gaia", question=r["Question"],
            expected_answer=str(r["Final answer"]).strip(), answer_type="freeform",
            tool_profile="web_compute",
            meta=dict(task_id=r["task_id"], level=3, has_file=bool(fname),
                      file_name=fname, n_steps=ann.get("Number of steps"),
                      tools=ann.get("Tools")))

        reason = _modality_reason(ann.get("Tools"), ext)
        if reason:
            rec["meta"]["excluded_reason"] = reason
            excluded.append(rec)
            continue

        if fname:                                   # stage the (text/doc) attachment locally
            dst = os.path.join(FILES_DIR, fname)
            if not os.path.exists(dst):
                src = hf_hub_download("gaia-benchmark/GAIA", f"2023/validation/{fname}",
                                      repo_type="dataset", token=hf_token())
                with open(src, "rb") as a, open(dst, "wb") as b:
                    b.write(a.read())
            rec["meta"]["file_local"] = os.path.relpath(dst, REPO_ROOT)
        evaluated.append(rec)

    evaluated.sort(key=lambda x: x["id"])
    excluded.sort(key=lambda x: x["id"])
    write_tasks(os.path.join(HERE, "tasks.jsonl"), evaluated)
    write_tasks(os.path.join(HERE, "excluded_vision.jsonl"), excluded)

    n_file = sum(1 for t in evaluated if t["meta"]["has_file"])
    print(f"  EVALUATED {len(evaluated)}  ({len(evaluated)-n_file} text-only + {n_file} doc-attachment)")
    print(f"  EXCLUDED  {len(excluded)} (vision/video/audio):")
    for t in excluded:
        print(f"    {t['id']}  {t['meta']['excluded_reason']}")


if __name__ == "__main__":
    build()
