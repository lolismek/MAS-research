'''
Entry point for the Sudoku application.
Uses a Tkinter GUI when available; otherwise falls back to a console demo so the
program runs smoothly even in Python builds without _tkinter installed.
'''
try:
    import tkinter as tk
    from sudoku_game import SudokuGame
    def main():
        root = tk.Tk()
        root.title("Classic Sudoku")
        root.resizable(False, False)
        SudokuGame(root)
        root.mainloop()
except ModuleNotFoundError:
    tk = None
    def main():
        from sudoku_utils import generate_puzzle, is_board_valid, board_is_complete
        print("Tkinter is not available in this Python environment.")
        print("Launching a minimal console fallback instead.\n")
        puzzle, solution = generate_puzzle(empty_cells=45)
        def render(board):
            for r in range(9):
                row = []
                for c in range(9):
                    val = board[r][c]
                    row.append(str(val) if val != 0 else ".")
                    if c in (2, 5):
                        row.append("|")
                print(" ".join(row))
                if r in (2, 5):
                    print("-" * 21)
        print("Puzzle:")
        render(puzzle)
        print("\nSolution is generated and valid:", is_board_valid(solution))
        print("Puzzle complete:", board_is_complete(puzzle))
if __name__ == "__main__":
    main()