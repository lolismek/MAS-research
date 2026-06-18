# Gomoku User Manual

A standard 15×15 Gomoku game implemented in Python with both a graphical interface and a command-line fallback.

---

## 1. Overview

Gomoku is a two-player board game where players alternate placing stones on a 15×15 board.

- **Black** moves first
- Players take turns placing one stone at a time
- The goal is to form an **unbroken row of five stones**
  - horizontally
  - vertically
  - diagonally

This application provides:

- A **Tkinter GUI** for interactive play
- A **CLI version** for terminal-based play
- Automatic **win detection**
- **Draw detection** when the board is full

---

## 2. Main Features

### 🎮 Game Rules
- Standard 15×15 board
- Two players: Black and White
- Alternate turns
- Invalid moves are rejected
- Game ends when a player gets five in a row

### 🖥️ GUI Mode
- Click intersections on the board to place stones
- Visual board with grid lines and star points
- Highlights the most recent move
- Displays status messages and game-over dialogs
- Supports starting a new game

### ⌨️ CLI Mode
- Play in a terminal
- Enter moves using row and column coordinates
- Prints the full board after each turn
- Supports quitting anytime

### ✅ Environment-Friendly Startup
- If Tkinter is available, the app uses the GUI
- If GUI cannot be launched, it falls back to CLI
- If no interactive input is available, it exits gracefully

---

## 3. File Structure

The application consists of the following files:

- `main.py`  
  Main entry point. Launches GUI or CLI depending on the environment.

- `gomoku_game.py`  
  Core game logic, rules, win detection, draw detection, and CLI gameplay.

- `gomoku_gui.py`  
  Tkinter-based graphical interface.

---

## 4. Installation

## 4.1 Requirements

- Python **3.9+** recommended
- No third-party packages are required

### Optional Dependency
- `tkinter`  
  Usually included with standard Python installations on Windows and macOS
  - On some Linux distributions, it must be installed separately

---

## 4.2 Install Python

If Python is not installed, download it from:

- https://www.python.org/downloads/

Verify installation:

```bash
python --version
```

or:

```bash
python3 --version
```

---

## 4.3 Install Tkinter

### Windows / macOS
Tkinter is usually included automatically with Python.

### Ubuntu / Debian
Install Tkinter with:

```bash
sudo apt-get update
sudo apt-get install python3-tk
```

### Fedora
```bash
sudo dnf install python3-tkinter
```

### Arch Linux
```bash
sudo pacman -S tk
```

---

## 5. How to Run

From the project directory, run:

```bash
python main.py
```

or, depending on your system:

```bash
python3 main.py
```

### What happens when you run it?
- If Tkinter is available and the environment supports GUI display, the graphical game opens
- If GUI cannot start, the program falls back to the terminal version
- If neither GUI nor interactive terminal input is available, it exits with a friendly message

---

## 6. How to Play

## 6.1 Playing in GUI Mode

### Start the game
Run:

```bash
python main.py
```

### Make a move
- Click near any board intersection
- A black or white stone will appear depending on the current player
- Players alternate automatically

### Winning
- The first player to place **five consecutive stones** in a row wins

### Restarting
- Click **New Game** to reset the board

### Game over
- When someone wins, a dialog box appears
- If the board fills completely without a winner, the game ends in a draw

---

## 6.2 Playing in CLI Mode

If the GUI is unavailable, the game runs in the terminal.

### Start the game
```bash
python main.py
```

### Enter moves
Moves must be entered as:

```text
row col
```

where:
- `row` is the row index
- `col` is the column index
- Indices are **0-based**
- Valid values range from **0 to 14**

### Example
```text
7 7
```

This places a stone at row 7, column 7.

### Other commands
- `quit` or `exit` — leave the game

### Invalid input
If you enter something invalid, the program will prompt you again.

---

## 7. Game Rules Details

### Board
- Size: **15 rows × 15 columns**
- Coordinates start from `0`

### Players
- Black: plays first
- White: plays second

### Legal Move Conditions
A move is legal only if:
- the game has not already ended
- the position is inside the board
- the chosen cell is empty

### Win Condition
A player wins if they create five or more stones in a continuous line:
- horizontal
- vertical
- diagonal down-right
- diagonal down-left

### Draw Condition
A draw occurs if:
- the board is full
- no player has won

---

## 8. GUI Usage Guide

The graphical interface contains:

### Board Area
- A wood-colored 15×15 board
- Grid intersections for placing stones
- Nine star points shown as black dots

### Status Bar
Displays:
- current player
- winner message
- draw state

### New Game Button
- Clears the board
- Resets turn order
- Starts a fresh match

### Last Move Highlight
- The most recent stone is marked with a red ring

---

## 9. CLI Usage Guide

The command-line version displays:
- the board after each turn
- the current player prompt
- move validation messages
- game result messages

### Stone Symbols
- `●` = Black stone
- `○` = White stone
- `·` = Empty intersection

### Example CLI Session
```text
Gomoku (15x15)
Enter moves as: row col  (0-based indices, e.g., 7 7)
Type 'quit' to exit.

   0  1  2  3  4  5  6  7  8  9 10 11 12 13 14
 0 · · · · · · · · · · · · · · ·
 1 · · · · · · · · · · · · · · ·
 ...
 7 · · · · · · · ● · · · · · · ·
 ...
Black's move:
```

---

## 10. Troubleshooting

### GUI does not open
Possible reasons:
- Tkinter is not installed
- You are running in a headless environment
- Your system does not support graphical windows

Solution:
- Install Tkinter
- Run the application on a machine with a desktop environment
- Use CLI mode instead

### “Illegal move. Try again.”
This means:
- you clicked an occupied location
- or in CLI mode, you entered an invalid coordinate
- or the move is outside the board

### “No interactive input is available”
This happens when:
- running in an automated environment
- stdin is not attached to a terminal

The program will exit safely in that case.

---

## 11. Development Notes

- The game logic is separated from the interface
- Win detection checks all four Gomoku directions
- The application is designed to be robust in environments where GUI support may not exist

---

## 12. Quick Start

```bash
python main.py
```

If the GUI opens:
- click intersections to play

If the terminal version opens:
- type moves like `7 7`

---

## 13. Summary

This Gomoku application lets two players enjoy the classic five-in-a-row game on a standard 15×15 board.

- Easy to run
- No external dependencies required
- GUI and CLI supported
- Clear win and draw detection

Enjoy playing Gomoku!