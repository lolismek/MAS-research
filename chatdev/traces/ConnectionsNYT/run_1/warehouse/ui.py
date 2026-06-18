'''
tkinter graphical user interface for the daily puzzle game
'''
from __future__ import annotations
try:
    import tkinter as tk
    from tkinter import messagebox
except Exception as exc:  # pragma: no cover
    tk = None  # type: ignore
    messagebox = None  # type: ignore
from datetime import date
from game_logic import PuzzleGameEngine
from puzzle_data import PuzzleRepository
DIFFICULTY_COLORS = {
    "yellow": "#f7d046",
    "green": "#9ad67a",
    "blue": "#7db7ff",
    "purple": "#c6a0ff",
}
class _HeadlessPuzzleApp:
    """
    Minimal fallback app used when Tkinter is unavailable.
    It keeps the program executable in environments lacking _tkinter, while
    clearly informing the user how to run the full GUI version.
    """
    def run(self) -> None:
        print("Daily Word Group Puzzle")
        print("GUI unavailable: Tkinter/_tkinter could not be imported.")
        print("Install a Python build with Tk support to play the graphical game.")
if tk is None:
    PuzzleApp = _HeadlessPuzzleApp
else:
    class PuzzleApp:
        """Tkinter-based application for the word grouping puzzle."""
        def __init__(self) -> None:
            self.root = tk.Tk()
            self.root.title("Daily Word Group Puzzle")
            self.root.geometry("900x720")
            self.root.minsize(820, 650)
            self.repo = PuzzleRepository()
            self.puzzle = self.repo.get_daily_puzzle(date.today())
            self.engine = PuzzleGameEngine(self.puzzle)
            self.word_buttons: dict[str, tk.Button] = {}
            self.status_var = tk.StringVar(value="Find four groups of four words.")
            self.mistakes_var = tk.StringVar()
            self.selected_var = tk.StringVar()
            self.daily_var = tk.StringVar()
            self.feedback_var = tk.StringVar()
            self._build_ui()
            self._render_grid()
            self._refresh_ui()
        def run(self) -> None:
            """Run the Tkinter main loop."""
            self.root.mainloop()
        def _build_ui(self) -> None:
            header = tk.Frame(self.root, pady=10)
            header.pack(fill="x")
            title = tk.Label(
                header,
                text="Daily Word Group Puzzle",
                font=("Arial", 22, "bold"),
            )
            title.pack()
            self.daily_var.set(f"Puzzle for {date.today().isoformat()}")
            daily_label = tk.Label(header, textvariable=self.daily_var, font=("Arial", 11))
            daily_label.pack()
            status_label = tk.Label(
                header,
                textvariable=self.status_var,
                font=("Arial", 12, "bold"),
                fg="#333333",
            )
            status_label.pack(pady=(6, 0))
            info = tk.Frame(self.root, pady=8)
            info.pack(fill="x")
            tk.Label(info, textvariable=self.mistakes_var, font=("Arial", 12)).pack(side="left", padx=20)
            tk.Label(info, textvariable=self.selected_var, font=("Arial", 12)).pack(side="left", padx=20)
            controls = tk.Frame(self.root, pady=8)
            controls.pack(fill="x")
            shuffle_btn = tk.Button(controls, text="Shuffle", command=self._on_shuffle, width=12)
            shuffle_btn.pack(side="left", padx=10)
            submit_btn = tk.Button(controls, text="Submit Guess", command=self._on_submit, width=12)
            submit_btn.pack(side="left", padx=10)
            clear_btn = tk.Button(controls, text="Clear Selection", command=self._clear_selection, width=14)
            clear_btn.pack(side="left", padx=10)
            feedback = tk.Label(
                self.root,
                textvariable=self.feedback_var,
                font=("Arial", 12, "bold"),
                pady=8,
            )
            feedback.pack(fill="x")
            self.grid_frame = tk.Frame(self.root, padx=20, pady=20)
            self.grid_frame.pack(expand=True, fill="both")
            self.solution_frame = tk.Frame(self.root, padx=20, pady=10)
            self.solution_frame.pack(fill="x")
        def _render_grid(self) -> None:
            """
            Render the active 4x4 board from the current unsolved word list.
            Solved words are excluded from the interactive board, ensuring the grid
            remains readable and consistent after shuffles and successful guesses.
            """
            for widget in self.grid_frame.winfo_children():
                widget.destroy()
            self.word_buttons.clear()
            words = self.engine.state.shuffled_words
            for i, word in enumerate(words):
                r, c = divmod(i, 4)
                btn = tk.Button(
                    self.grid_frame,
                    text=word,
                    width=18,
                    height=3,
                    wraplength=120,
                    command=lambda w=word: self._toggle_word(w),
                    relief="raised",
                    font=("Arial", 11, "bold"),
                )
                btn.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")
                self.word_buttons[word] = btn
            for i in range(4):
                self.grid_frame.grid_columnconfigure(i, weight=1)
                self.grid_frame.grid_rowconfigure(i, weight=1)
            self._update_word_styles()
        def _update_word_styles(self) -> None:
            for word, btn in self.word_buttons.items():
                if self.engine.is_word_solved(word):
                    btn.config(state="disabled", bg="#d9d9d9", fg="#777777", relief="sunken")
                elif word in self.engine.state.selected_words:
                    btn.config(state="normal", bg="#444444", fg="white", relief="sunken")
                else:
                    btn.config(state="normal", bg="SystemButtonFace", fg="black", relief="raised")
        def _toggle_word(self, word: str) -> None:
            """
            Toggle a word selection and provide immediate feedback.
            When the fourth word is selected, the UI clearly indicates that the
            guess is ready to submit. Selection of a fifth word is explicitly
            blocked by the engine and reflected in the feedback bar.
            """
            changed, message = self.engine.toggle_selection(word)
            self.feedback_var.set(message)
            self._refresh_ui()
            if changed and len(self.engine.state.selected_words) == 4:
                self.feedback_var.set("4 selected — submit to check the group.")
        def _clear_selection(self) -> None:
            self.engine.state.selected_words.clear()
            self._refresh_ui()
            self.feedback_var.set("Selection cleared.")
        def _on_shuffle(self) -> None:
            if self.engine.state.game_over:
                return
            self.engine.shuffle()
            self._render_grid()
            self._refresh_ui()
            self.feedback_var.set("Words shuffled.")
        def _on_submit(self) -> None:
            success, message, difficulty = self.engine.submit_guess()
            self.feedback_var.set(message)
            if success and difficulty:
                category, _, words = self.engine.state.solved_groups[-1]
                self._show_solved_group(category, difficulty, words)
            self._refresh_ui()
            if self.engine.state.game_over:
                self._end_game()
        def _show_solved_group(self, category: str, difficulty: str, words: list[str]) -> None:
            color = DIFFICULTY_COLORS.get(difficulty, "#dddddd")
            frame = tk.Frame(self.solution_frame, bg=color, padx=10, pady=8, bd=1, relief="solid")
            frame.pack(fill="x", pady=4)
            text = f"{category} ({difficulty.upper()}): " + ", ".join(words)
            tk.Label(frame, text=text, bg=color, font=("Arial", 11, "bold")).pack(anchor="w")
        def _refresh_ui(self) -> None:
            self.mistakes_var.set(f"Mistakes: {self.engine.state.mistakes}/{self.engine.state.max_mistakes}")
            self.selected_var.set(f"Selected: {len(self.engine.state.selected_words)}/4")
            self._update_word_styles()
            if self.engine.state.game_over:
                if self.engine.state.won:
                    self.status_var.set("You solved the puzzle!")
                else:
                    self.status_var.set("No more mistakes allowed.")
            else:
                self.status_var.set("Find four groups of four words.")
        def _end_game(self) -> None:
            for btn in self.word_buttons.values():
                btn.config(state="disabled")
            if messagebox is None:
                return
            if self.engine.state.won:
                messagebox.showinfo("Puzzle Complete", "Congratulations! You solved all four groups.")
                self.feedback_var.set("You won!")
            else:
                solution_text = self._build_solution_text()
                messagebox.showwarning("Game Over", solution_text)
                self.feedback_var.set("Game over.")
        def _build_solution_text(self) -> str:
            lines = ["The correct groups were:"]
            for category, difficulty, words in self.puzzle.groups:
                lines.append(f"- {category} [{difficulty.upper()}]: {', '.join(words)}")
            return "\n".join(lines)