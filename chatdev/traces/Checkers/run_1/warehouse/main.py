'''
main entry point for the checkers game application
'''
from gui import CheckersGUI
def main():
    """Start the Checkers application."""
    app = CheckersGUI()
    app.run()
if __name__ == "__main__":
    main()