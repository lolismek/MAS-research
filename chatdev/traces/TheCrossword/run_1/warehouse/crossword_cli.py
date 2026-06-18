'''
Console-based crossword puzzle application.
Used as a fallback when the Tkinter GUI cannot be loaded in the runtime
environment.
'''
from puzzle import CrosswordPuzzle
class CrosswordCLI:
    """Simple terminal interface for the crossword puzzle."""
    def __init__(self, puzzle: CrosswordPuzzle):
        self.puzzle = puzzle
    def _render(self):
        """Print the current crossword grid to the console."""
        print("\nCrossword Grid:")
        for r in range(self.puzzle.rows):
            row_cells = []
            for c in range(self.puzzle.cols):
                if not self.puzzle.valid_cell(r, c):
                    row_cells.append("#")
                else:
                    letter = self.puzzle.display_letter(r, c)
                    row_cells.append(letter if letter else ".")
            print(" ".join(row_cells))
        print()
    def _render_clues(self):
        """Print all clues grouped by direction."""
        print("Across:")
        for clue in sorted(
            [c for c in self.puzzle.clues if c.direction.lower() == "across"],
            key=lambda c: c.number,
        ):
            print(f"  {clue.number}. {clue.clue}")
        print("\nDown:")
        for clue in sorted(
            [c for c in self.puzzle.clues if c.direction.lower() == "down"],
            key=lambda c: c.number,
        ):
            print(f"  {clue.number}. {clue.clue}")
    def run(self):
        """Run the interactive console loop."""
        print("Tkinter is unavailable in this environment.")
        print("Starting the crossword puzzle in console mode instead.")
        self._render_clues()
        while not self.puzzle.is_complete():
            self._render()
            raw_number = input("Clue number (or 'q' to quit): ").strip()
            if raw_number.lower() in {"q", "quit", "exit"}:
                print("Goodbye.")
                return
            raw_direction = input("Direction (across/down): ").strip().lower()
            raw_answer = input("Answer: ").strip()
            try:
                number = int(raw_number)
            except ValueError:
                print("Invalid clue number. Please enter an integer.")
                continue
            if raw_direction not in {"across", "down"}:
                print("Direction must be 'across' or 'down'.")
                continue
            if self.puzzle.submit_answer(number, raw_direction, raw_answer):
                print("Correct!")
            else:
                print("Incorrect answer or conflicting letters.")
        self._render()
        print("Congratulations! You completed the crossword puzzle.")