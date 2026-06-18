'''
Main entry point for the simplified Monopoly Go-style game.
This version gracefully falls back to a command-line interface when Tkinter
is unavailable in the execution environment.
'''
from ui import MonopolyGUI
def main():
    app = MonopolyGUI()
    app.run()
if __name__ == "__main__":
    main()