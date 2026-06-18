"""
Entry point for the Strands-like puzzle application.
"""
def main() -> None:
    """Start the application safely, even when Tk is unavailable."""
    try:
        from app import StrandsApp
        app = StrandsApp()
        app.run()
    except ModuleNotFoundError as exc:
        # Tkinter is not available in this environment.
        # Provide a graceful fallback instead of crashing.
        if exc.name == "_tkinter":
            print(
                "Strands Puzzle cannot start because Tkinter is not installed in this Python environment."
            )
            print("Please install a Python build with Tk support to run the GUI application.")
            return
        raise
if __name__ == "__main__":
    main()