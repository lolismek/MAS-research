'''
main application entry point
'''
from __future__ import annotations
import os
from typing import Any
def _load_puzzle_app() -> Any:
    """
    Load the PuzzleApp implementation.
    Tkinter is not always available in headless or minimal Python builds.
    This helper falls back to a lightweight CLI-compatible message if the GUI
    backend cannot be imported, allowing the program to execute smoothly rather
    than crashing at startup.
    """
    try:
        from ui import PuzzleApp  # type: ignore
        return PuzzleApp
    except Exception as exc:
        # Defer failure to runtime with a graceful fallback.
        return None, exc
def main() -> None:
    """Launch the daily word-grouping puzzle game."""
    loaded = _load_puzzle_app()
    # Normal GUI path.
    if loaded is not None and not isinstance(loaded, tuple):
        app = loaded()
        app.run()
        return
    # Fallback path when Tkinter/_tkinter is unavailable.
    _, exc = loaded
    print("Daily Word Group Puzzle could not start the GUI.")
    print(f"Reason: {exc}")
    print("This environment does not provide a working Tkinter installation.")
    print("Please run the game in a Python environment with Tk support enabled.")
if __name__ == "__main__":
    main()