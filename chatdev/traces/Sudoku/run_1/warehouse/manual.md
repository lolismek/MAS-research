```markdown
# Classic Sudoku Puzzle Game

A simple and elegant **classic Sudoku** application built in Python.

The game uses a **9x9 grid** where every:

- **row**
- **column**
- **3x3 subgrid**

must contain the digits **1 through 9 exactly once**.

The player can enter numbers into empty cells, the game checks for mistakes as you play, and it confirms when the puzzle is completed correctly.

---

## Features

- Classic 9x9 Sudoku gameplay
- Randomly generated puzzle with a unique solution
- Input validation for digits `1` to `9`
- Mistake detection for invalid moves
- Completion checking and win notification
- "New Game" button to start a fresh puzzle
- "Reveal Solution" button to display the answer
- Tkinter GUI interface
- Console fallback if Tkinter is unavailable

---

## Project Structure

```text
main.py
sudoku_game.py
sudoku_utils.py
```

### File Overview

- **`main.py`**
  - Program entry point
  - Launches the Tkinter GUI if available
  - Falls back to a console demo if Tkinter cannot be used

- **`sudoku_game.py`**
  - Contains the `SudokuGame` GUI class
  - Manages the game board, input handling, validation, and UI actions

- **`sudoku_utils.py`**
  - Provides Sudoku logic utilities:
    - board validation
    - solving
    - puzzle generation
    - uniqueness checking
    - completion detection

---

## Requirements

- **Python 3.8+** recommended
- Standard library only for the GUI version
- `tkinter` must be available for the graphical interface

### Important Note About Tkinter

`tkinter` is included with most standard Python installations, but on some Linux systems it may need to be installed separately.

Examples:

- **Ubuntu / Debian**
  ```bash
  sudo apt-get update
  sudo apt-get install python3-tk
  ```

- **Fedora**
  ```bash
  sudo dnf install python3-tkinter
  ```

- **Arch Linux**
  ```bash
  sudo pacman -S tk
  ```

- **Windows / macOS**
  - Tkinter is usually included with the official Python installer.
  - If missing, reinstall Python from the official source:
    - https://www.python.org/downloads/

---

## Installation

### 1. Download the files

Make sure the following files are in the same folder:

```text
main.py
sudoku_game.py
sudoku_utils.py
```

### 2. Verify Python installation

Check your Python version:

```bash
python --version
```

or

```bash
python3 --version
```

### 3. Install Tkinter if needed

If the GUI does not open and you receive a Tkinter-related error, install the Tk support package for your operating system using the instructions above.

---

## How to Run

From the project directory, run:

```bash
python main.py
```

or, depending on your system:

```bash
python3 main.py
```

### If Tkinter is available

The graphical Sudoku window will open.

### If Tkinter is not available

The program will automatically switch to a minimal console fallback mode and print a generated puzzle in the terminal.

---

## How to Play

### Game Objective

Fill the entire 9x9 Sudoku grid so that:

- each **row** contains the digits 1–9 exactly once
- each **column** contains the digits 1–9 exactly once
- each **3x3 box** contains the digits 1–9 exactly once

### Starting the Game

When the game starts:

- some cells are already filled in
- these cells are fixed and cannot be edited
- empty cells are where the player enters numbers

### Entering Numbers

- Click on an empty cell
- Type a number from **1** to **9**
- The game only allows one digit at a time
- Empty cells can be cleared by deleting the number

### Mistake Checking

The game checks your entries in two ways:

1. **Immediate feedback**
   - Cells may turn:
     - **green** if the entry is valid
     - **red** if the entry is invalid

2. **Check Puzzle button**
   - Validates the whole board
   - Reports the first mistake found
   - Confirms if the board is complete and correct

### Winning the Game

When all cells are filled and the board satisfies Sudoku rules, the game will:

- show a success message
- update the status text with a congratulatory message

---

## GUI Controls

### Check Puzzle
Validates all user-filled cells and checks whether the puzzle has been completed correctly.

### New Game
Generates a brand-new Sudoku puzzle.

### Reveal Solution
Shows the correct completed Sudoku board.

---

## Interface Guide

### Board Colors

- **White**: empty cell or normal editable cell
- **Gray**: fixed clue cell from the puzzle
- **Green**: valid entry
- **Red**: invalid entry
- **Light blue**: revealed solution cell

### Status Message

At the bottom of the window, the status line provides guidance such as:

- “Fill the grid. Red cells indicate mistakes.”
- “So far so good. Keep going!”
- “Congratulations! You completed the Sudoku puzzle.”

---

## Game Logic Overview

The application enforces Sudoku rules using internal validation functions:

- **Row validation**: no repeated digits in a row
- **Column validation**: no repeated digits in a column
- **Box validation**: no repeated digits in any 3x3 subgrid
- **Move validation**: checks whether a specific number can be placed in a specific cell
- **Completion validation**: checks whether the whole board is filled and valid

The puzzle generator also ensures that each generated puzzle has a **unique solution**.

---

## Console Fallback Mode

If Tkinter is not available, the application does not crash. Instead, it:

- generates a Sudoku puzzle
- prints it in the terminal
- shows whether the solution is valid
- shows whether the puzzle is complete

This fallback is mainly for compatibility testing and basic demonstration.

---

## Troubleshooting

### The window does not open
- Check whether Tkinter is installed
- Ensure you are running the correct Python interpreter
- Try:
  ```bash
  python3 main.py
  ```

### I cannot type in a clue cell
- This is expected
- Pre-filled cells are disabled so the puzzle cannot be altered accidentally

### The puzzle generation is slow
- Puzzle generation may take a few moments because the program ensures a unique solution
- This is normal behavior

### I entered a number, but it turns red
- The number conflicts with another number in the same row, column, or 3x3 box
- Remove the conflicting entry and try again

---

## Example Workflow

1. Launch the game
2. Study the fixed numbers on the board
3. Enter a number in an empty cell
4. Watch the cell color for feedback
5. Continue filling the board
6. Click **Check Puzzle**
7. If correct, the game will congratulate you
8. Start a **New Game** if you want to play again

---

## Known Limitations

- This version uses a simple GUI with text-based grid input
- It does not include:
  - hints
  - timer
  - difficulty selection
  - undo/redo
  - note-taking/pencil marks

These features can be added in future versions.

---

## Credits

Created as a classic Sudoku puzzle application in Python.

Enjoy the game and good luck solving the puzzle!
```