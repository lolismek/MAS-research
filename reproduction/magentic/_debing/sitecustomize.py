"""Auto-loaded by Python at interpreter startup when this directory is on
PYTHONPATH. ``run_task.py`` puts ``reproduction/magentic/_debing`` on the
scenario.py subprocess's PYTHONPATH so the de-Bing monkeypatch is installed
before MultimodalWebSurfer ever runs — without touching site-packages.

Gate on autogen_ext: this directory may land on PYTHONPATH for unrelated
interpreters too (e.g. conda's own helper processes). Only an interpreter that
can import autogen_ext is a Magentic-One process worth patching; others skip
silently. But once we commit to patching, fail loud — never silently run the
original Bing path, which would mislabel a Bing run as a de-Bing'd one."""
import importlib.util

if importlib.util.find_spec("autogen_ext") is not None:
    try:
        import websurfer_debing

        websurfer_debing.apply()
    except Exception as e:  # noqa: BLE001 - surface any real failure and stop the run
        import sys

        print(f"[de-bing] FAILED to apply: {e!r}", file=sys.stderr, flush=True)
        raise
