```md
# Strands Puzzle

A Strands-like word search game built with Python and Tkinter.

Players uncover themed words hidden in a 6×8 letter grid by connecting adjacent letters in any direction. Each puzzle has a special **spangram** that touches two opposite sides of the board and describes the theme. Theme words are highlighted in **blue**, while the spangram is highlighted in **yellow**.

---

## Features

- 6×8 puzzle board
- Theme-based word finding
- Special **spangram** word that spans opposite sides of the board
- Adjacent-letter path selection in any direction:
  - horizontal
  - vertical
  - diagonal
  - direction changes allowed mid-word
- Non-theme word tracking
- Hint system:
  - Every 3 non-theme words unlock 1 hint
- Board completion requirement:
  - the puzzle is complete only when all theme words are found and the entire board is filled by the solution paths
- Multiple built-in puzzles
- Undo support for the last found theme word
- Safe startup fallback when Tkinter is unavailable

---

## Requirements

- Python 3.10 or newer is recommended
- Tkinter support for the GUI

> If Tkinter is not installed in your Python environment, the application will print a friendly message and exit gracefully.

---

## Installation

### 1. Clone or download the project

Place all project files in the same folder:

- `main.py`
- `app.py`
- `game.py`
- `puzzles.py`
- `utils.py`

### 2. Install dependencies

This project uses only the Python standard library, so there are no external packages to install.

If needed, ensure Tkinter is available:

#### On Ubuntu/Debian
```bash
sudo apt-get install python3-tk
```

#### On Fedora
```bash
sudo dnf install python3-tkinter
```

#### On macOS
Tkinter is usually included with the official Python installer from python.org.

#### On Windows
Tkinter is typically included with the standard Python installer.

---

## How to Run

From the project folder, run:

```bash
python main.py
```

If your system uses `python3`, use:

```bash
python3 main.py
```

---

## What the Application Does

When launched, the game opens a window containing:

- the puzzle theme
- a dropdown to select a puzzle
- buttons for:
  - **New Game**
  - **Clear**
  - **Undo**
  - **Hint**
- a 6×8 letter board
- status information showing:
  - found theme words
  - non-theme words
  - hints available
  - whether the board is complete

---

## Game Rules

### 1. Find Theme Words
You must find all words that belong to the puzzle’s theme.

Example themes included in the demo:
- Kitchen Tools
- Ocean Life

### 2. Find the Spangram
Each puzzle includes one **spangram**:
- it is a special word or phrase
- it touches two opposite sides of the grid
- it usually describes the theme category

### 3. Build Words by Connecting Adjacent Letters
Words are formed by selecting letters that are adjacent in any of the 8 directions:

- up
- down
- left
- right
- diagonals

You may also change direction mid-word.

### 4. No Overlapping Solution Paths
The puzzle solution is designed so that all theme words and the spangram together fill the board without overlap.

### 5. Earn Hints with Non-Theme Words
If you find a word that is not part of the theme:

- the game records it as a non-theme word
- every 3 non-theme words unlock 1 hint

### 6. Complete the Puzzle
The puzzle is only complete when:

- all theme words are found
- the spangram is found
- all board cells are filled by the solution paths

---

## How to Play

### Selecting Letters
- Click a letter cell to start a word.
- Drag or click adjacent cells to continue the word.
- Release the mouse button to submit the selected path.

### Valid Selection Rules
A valid word path must:
- stay within the board
- move only through adjacent cells
- not repeat cells within the same word
- match one of the puzzle’s predefined solution paths

### Colors
- **Blue**: themed word found
- **Yellow**: spangram found
- **White outline**: currently selected cells

---

## Controls

### New Game
Resets the current puzzle to its initial state.

### Clear
Clears the current selected path without changing puzzle progress.

### Undo
Removes the last found theme word or spangram from the board state.

### Hint
Shows one hint if at least one hint is available.

Hints are unlocked by finding 3 non-theme words.

---

## Puzzle Selection

Use the dropdown menu at the top to switch between available puzzles.

Available puzzles in this version:
- Kitchen Tools
- Ocean Life

When you switch puzzles:
- the board resets
- all progress is cleared
- the selected puzzle is loaded

---

## Example Gameplay Walkthrough

1. Launch the app.
2. Read the theme shown at the top.
3. Start selecting adjacent letters to form a word.
4. If the word is valid and part of the puzzle, it will highlight:
   - blue for a theme word
   - yellow if it is the spangram
5. If the word is not part of the theme:
   - it counts as a non-theme word
   - after every 3 non-theme words, a hint becomes available
6. Continue until all theme words are found and the full board is completed.

---

## Troubleshooting

### The program says Tkinter is missing
Install a Python build with Tk support.

### The window does not open
Check that:
- you are running the correct Python interpreter
- Tkinter is installed
- the project files are in the same folder

### A puzzle fails to load
The game validates all puzzle data strictly. If there is an issue, an error dialog will appear.

---

## Project Structure

- `main.py`  
  Application entry point

- `app.py`  
  Tkinter GUI and user interactions

- `game.py`  
  Puzzle state, validation, hints, and completion logic

- `puzzles.py`  
  Built-in puzzle definitions

- `utils.py`  
  Shared helper functions for word normalization and path validation

---

## Notes for Developers

This implementation is intentionally strict:

- all puzzles are validated at load time
- the board must be exactly 6 rows by 8 columns
- spangram paths must touch opposite sides of the board
- all solution paths must cover the entire board exactly once

This ensures puzzle integrity and makes the application reliable for gameplay.

---

## Summary

This Strands Puzzle app is a complete, playable Python/Tkinter implementation of a themed word-search game. Players can:

- find theme words
- discover the spangram
- earn hints
- switch puzzles
- track completion progress

Enjoy solving the board!
```