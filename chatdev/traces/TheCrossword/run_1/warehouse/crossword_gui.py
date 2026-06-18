'''
Tkinter GUI for the crossword puzzle application.
This file is loaded only when Tkinter is available, preventing startup
failure in environments missing the _tkinter module.
'''
import tkinter as tk
from tkinter import messagebox
class CrosswordGUI:
    """Interactive crossword puzzle GUI."""
    CELL_SIZE = 48
    def __init__(self, root, puzzle):
        self.root = root
        self.puzzle = puzzle
        self.root.title("Crossword Puzzle")
        self.clue_map = self.puzzle.get_clue_map()
        self.entries = {}
        self._build_layout()
        self.refresh_grid()
    def _build_layout(self):
        main = tk.Frame(self.root, padx=10, pady=10)
        main.pack(fill="both", expand=True)
        left = tk.Frame(main)
        left.pack(side="left", fill="both", expand=False, padx=(0, 15))
        right = tk.Frame(main)
        right.pack(side="right", fill="both", expand=True)
        title = tk.Label(left, text="Crossword Grid", font=("Arial", 14, "bold"))
        title.pack(anchor="w", pady=(0, 8))
        self.canvas = tk.Canvas(
            left,
            width=self.puzzle.cols * self.CELL_SIZE,
            height=self.puzzle.rows * self.CELL_SIZE,
            bg="white",
            highlightthickness=1,
            highlightbackground="#888",
        )
        self.canvas.pack()
        form = tk.LabelFrame(right, text="Enter Answer", padx=10, pady=10)
        form.pack(fill="x", pady=(0, 12))
        tk.Label(form, text="Clue Number:").grid(row=0, column=0, sticky="w", pady=4)
        self.number_var = tk.StringVar()
        tk.Entry(form, textvariable=self.number_var, width=12).grid(row=0, column=1, sticky="w", pady=4)
        tk.Label(form, text="Direction:").grid(row=1, column=0, sticky="w", pady=4)
        self.direction_var = tk.StringVar(value="across")
        direction_menu = tk.OptionMenu(form, self.direction_var, "across", "down")
        direction_menu.config(width=10)
        direction_menu.grid(row=1, column=1, sticky="w", pady=4)
        tk.Label(form, text="Answer:").grid(row=2, column=0, sticky="w", pady=4)
        self.answer_var = tk.StringVar()
        tk.Entry(form, textvariable=self.answer_var, width=24).grid(row=2, column=1, sticky="w", pady=4)
        tk.Button(form, text="Submit", command=self.submit).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        clues_frame = tk.LabelFrame(right, text="Clues", padx=10, pady=10)
        clues_frame.pack(fill="both", expand=True)
        across_label = tk.Label(clues_frame, text="Across", font=("Arial", 11, "bold"))
        across_label.pack(anchor="w")
        self.across_box = tk.Text(clues_frame, height=8, wrap="word")
        self.across_box.pack(fill="x", pady=(0, 10))
        self.across_box.configure(state="disabled")
        down_label = tk.Label(clues_frame, text="Down", font=("Arial", 11, "bold"))
        down_label.pack(anchor="w")
        self.down_box = tk.Text(clues_frame, height=8, wrap="word")
        self.down_box.pack(fill="x")
        self.down_box.configure(state="disabled")
        self.status_var = tk.StringVar(value="Enter a clue number, direction, and answer.")
        status = tk.Label(self.root, textvariable=self.status_var, anchor="w", padx=10, pady=6, fg="#333")
        status.pack(fill="x")
        self._populate_clues()
    def _populate_clues(self):
        across = []
        down = []
        for clue in sorted(self.puzzle.clues, key=lambda c: (c.direction.lower(), c.number)):
            line = f"{clue.number}. {clue.clue}"
            if clue.direction.lower() == "across":
                across.append(line)
            else:
                down.append(line)
        self._set_text(self.across_box, "\n".join(across))
        self._set_text(self.down_box, "\n".join(down))
    def _set_text(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")
    def refresh_grid(self):
        self.canvas.delete("all")
        for r in range(self.puzzle.rows):
            for c in range(self.puzzle.cols):
                x1 = c * self.CELL_SIZE
                y1 = r * self.CELL_SIZE
                x2 = x1 + self.CELL_SIZE
                y2 = y1 + self.CELL_SIZE
                if not self.puzzle.valid_cell(r, c):
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill="black", outline="black")
                else:
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill="white", outline="black")
                    letter = self.puzzle.display_letter(r, c)
                    if letter:
                        self.canvas.create_text(
                            x1 + self.CELL_SIZE / 2,
                            y1 + self.CELL_SIZE / 2,
                            text=letter,
                            font=("Arial", 16, "bold"),
                        )
        for clue in self.puzzle.clues:
            r, c = clue.start
            if self.puzzle.valid_cell(r, c):
                x = c * self.CELL_SIZE + 4
                y = r * self.CELL_SIZE + 3
                self.canvas.create_text(x, y, text=str(clue.number), anchor="nw", font=("Arial", 8, "bold"))
    def submit(self):
        number_text = self.number_var.get().strip()
        direction = self.direction_var.get().strip().lower()
        answer = self.answer_var.get().strip()
        if not number_text:
            messagebox.showerror("Input Error", "Please enter a clue number.")
            return
        try:
            number = int(number_text)
        except ValueError:
            messagebox.showerror("Input Error", "Clue number must be an integer.")
            return
        if direction not in {"across", "down"}:
            messagebox.showerror("Input Error", "Direction must be 'across' or 'down'.")
            return
        if not answer:
            messagebox.showerror("Input Error", "Please enter an answer.")
            return
        key = f"{number}-{direction}"
        if key not in self.clue_map:
            messagebox.showerror("Invalid Clue", f"No clue found for {number} {direction}.")
            return
        clue = self.clue_map[key]
        if self.puzzle.submit_answer(number, direction, answer):
            self.refresh_grid()
            self.status_var.set(f"Correct: {number} {direction} — {clue.clue}")
            self.answer_var.set("")
            if self.puzzle.is_complete():
                messagebox.showinfo("Completed", "Congratulations! You completed the crossword puzzle.")
                self.status_var.set("Puzzle complete!")
        else:
            messagebox.showerror("Incorrect", "That answer is not correct. Please try again.")
            self.status_var.set(f"Incorrect submission for {number} {direction}.")