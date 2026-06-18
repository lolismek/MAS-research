```markdown
# Tic-Tac-Toe Game Manual

A simple, user-friendly two-player Tic-Tac-Toe application built in Python.

## Overview

This application lets two players play the classic Tic-Tac-Toe game on a standard 3x3 grid.

### Main Features

- 3x3 game board
- Two-player alternating turns
- Player X starts first
- Winner detection
- Draw detection when the board is full
- Move tracking for both players
- Restart game support
- Graphical user interface using Tkinter
- Console fallback if Tkinter is unavailable

---

## Requirements

### Python Version
- Python 3.8 or later is recommended

### Dependencies
- **Tkinter** (usually included with standard Python installations)
  - If Tkinter is not available, the game automatically falls back to console mode.

No third-party packages are required.

---

## Installation

### 1. Download the Project

Make sure the following files are in the same directory:

- `main.py`
- `tic_tac_toe.py`

### 2. Check Python Installation

Verify Python is installed:

```bash
python --version
```

or

```bash
python3 --version
```

### 3. Install Tkinter if Needed

#### Windows
Tkinter is usually included with Python. If it is missing, reinstall Python from the official installer and ensure `tkinter` support is enabled.

#### macOS
Tkinter is generally included, but if the GUI does not open, install a Python distribution with Tk support such as the official Python installer from python.org.

#### Linux
Install Tkinter using your package manager:

```bash
sudo apt-get install python3-tk
```

For Fedora:

```bash
sudo dnf install python3-tkinter
```

For Arch Linux:

```bash
sudo pacman -S tk
```

---

## How to Run

From the project directory, run:

```bash
python main.py
```

If your system uses `python3`, run:

```bash
python3 main.py
```

### What Happens When You Run It

- If Tkinter is available and a window can be created, the graphical version opens.
- If Tkinter is unavailable or a GUI window cannot be created, the game runs in console mode.

---

## How to Play

### In GUI Mode

When the game starts, you will see:

- A title
- The current player's turn
- Move counters for X and O
- A 3x3 clickable board
- A restart button

### Gameplay Rules

1. Player **X** always goes first.
2. Players take turns clicking an empty cell.
3. X and O alternate automatically after each valid move.
4. The first player to get 3 marks in a row wins:
   - horizontally
   - vertically
   - diagonally
5. If all 9 cells are filled and no one wins, the game ends in a draw.

### After Game Ends

- A message box will announce the result:
  - `"Player X wins!"`
  - `"Player O wins!"`
  - `"It's a draw!"`
- All board cells become disabled after the game ends.
- Click **Restart Game** to begin a new match.

---

## Console Mode Usage

If the GUI cannot be launched, the game switches to console mode.

### How to Enter Moves

You will be prompted to enter a move as:

```text
row,col
```

Both row and column must be between `0` and `2`.

### Example

```text
1,2
```

This means:
- row = 1
- column = 2

### Console Controls

- Enter valid coordinates to place your mark.
- Invalid or occupied cells will be rejected.
- The game prints the board after each turn.
- The game ends automatically when:
  - a player wins, or
  - the board is full.

---

## Game Rules

### Board Layout

The board uses zero-based indexing:

| Row \ Col | 0 | 1 | 2 |
|----------|---|---|---|
| 0 | top-left | top-middle | top-right |
| 1 | middle-left | center | middle-right |
| 2 | bottom-left | bottom-middle | bottom-right |

### Winning Combinations

A player wins by placing three of their marks in:

- Any horizontal row
- Any vertical column
- Either diagonal

---

## Move Tracking

The application tracks the number of moves made by each player.

Displayed as:

```text
Moves - X: 2 | O: 1
```

This helps users monitor gameplay progress.

---

## Restarting the Game

### GUI Mode
Click the **Restart Game** button.

### Console Mode
Restart by closing and running the program again.

---

## Troubleshooting

### The game does not open a window
- Tkinter may not be installed.
- Your environment may be headless or not support GUI windows.
- The application will automatically use console mode in such cases.

### Invalid move not accepted
- Make sure the selected cell is empty.
- In console mode, ensure you use the correct format: `row,col`.

### Python command not found
- Install Python from the official website:
  - https://www.python.org/

---

## File Structure

```text
project/
├── main.py
└── tic_tac_toe.py
```

### `main.py`
Entry point of the application.

### `tic_tac_toe.py`
Contains:
- Game logic
- GUI implementation
- Console fallback

---

## Summary

This Tic-Tac-Toe application provides an easy-to-use way for two players to enjoy the classic game in either GUI or console mode. It is lightweight, requires no third-party dependencies, and works reliably across environments.

Enjoy the game!
```