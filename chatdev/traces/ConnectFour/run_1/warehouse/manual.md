```md
# Connect Four Console Game

A simple, standard two-player Connect Four game implemented in Python.

Two players alternate dropping discs into a 7-column, 6-row grid. The goal is to connect four discs in a row horizontally, vertically, or diagonally before your opponent does.

---

## Table of Contents

- [What This Software Does](#what-this-software-does)
- [Main Features](#main-features)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [How to Run](#how-to-run)
- [How to Play](#how-to-play)
- [Game Rules](#game-rules)
- [Input Validation](#input-validation)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Notes for Developers](#notes-for-developers)

---

## What This Software Does

This application provides a complete console-based Connect Four experience:

- Displays a 7-column, 6-row board
- Lets two players take turns entering a column number
- Drops a disc into the lowest available position in the selected column
- Detects winning conditions:
  - Horizontal
  - Vertical
  - Diagonal `/`
  - Diagonal `\`
- Detects a draw when the board is full
- Rejects invalid moves, such as:
  - Non-numeric input
  - Out-of-range columns
  - Full columns

---

## Main Features

### 1. Interactive Console Gameplay
The game runs in the terminal and prompts players to choose a column each turn.

### 2. Standard Connect Four Rules
- 7 columns
- 6 rows
- 2 players
- Win by connecting 4 discs in a line

### 3. Automatic Turn Switching
After a valid move, the game automatically switches to the next player.

### 4. Win and Draw Detection
The game ends immediately when:
- A player makes a winning move, or
- The board becomes full with no winner

### 5. Input Validation
The software checks whether the selected column:
- Is a valid number
- Is within the allowed range
- Has available space

---

## Project Structure

The provided code is organized into the following files:

- `main.py`  
  Entry point that starts the game.

- `game.py`  
  Contains the game logic, board state, win detection, move validation, and board rendering.

- `cli.py`  
  Handles the console user interface and player interaction.

- `gui.py`  
  Placeholder module for possible future graphical interface support.

---

## Installation

### Requirements
- Python 3.10 or later is recommended
- No external third-party packages are required

### Environment Setup
Since the game uses only the Python standard library, installation is straightforward.

#### Option 1: Use your system Python
Check your Python version:

```bash
python --version
```

or on some systems:

```bash
python3 --version
```

#### Option 2: Create a virtual environment
It is recommended to run the game inside a virtual environment:

```bash
python -m venv .venv
```

Activate it:

- **Windows**
  ```bash
  .venv\Scripts\activate
  ```

- **macOS / Linux**
  ```bash
  source .venv/bin/activate
  ```

No additional dependencies need to be installed.

---

## How to Run

From the project directory, run:

```bash
python main.py
```

If your system requires `python3`, use:

```bash
python3 main.py
```

The game will start in the terminal and display instructions.

---

## How to Play

1. The board is displayed with columns numbered **1 to 7**.
2. Players take turns entering the number of the column where they want to drop a disc.
3. The disc falls to the lowest empty space in that column.
4. Players alternate turns automatically.
5. The game ends when one player connects four discs or when the board is full.

### Symbols Used
- `X` = Player 1
- `O` = Player 2
- `.` = Empty cell

---

## Game Rules

### Board Layout
The board contains:
- 7 columns
- 6 rows

### Turn Order
- Player 1 starts
- Players alternate after each successful move

### Winning
A player wins by placing four discs in a continuous line:
- Horizontally
- Vertically
- Diagonally upward `/`
- Diagonally downward `\`

### Draw
If the entire board is filled and no player has won, the game ends in a draw.

---

## Input Validation

The game validates user input to prevent invalid moves.

### Valid Inputs
- Numbers from **1 to 7**

### Invalid Inputs
The game will reject:
- Letters or words
- Blank input
- Numbers less than 1
- Numbers greater than 7
- Moves in a column that is already full

### Example Invalid Messages
- `Invalid input. Please enter a number.`
- `Invalid column. Please choose a number from 1 to 7.`
- `Column X is invalid or full. Choose another column.`

---

## Examples

### Example Start of Game

```text
Welcome to Connect Four!
Players take turns choosing a column from 1 to 7.
Player 1 = X, Player 2 = O

1  2  3  4  5  6  7
.  .  .  .  .  .  .
.  .  .  .  .  .  .
.  .  .  .  .  .  .
.  .  .  .  .  .  .
.  .  .  .  .  .  .
.  .  .  .  .  .  .

Player 1 choose a column (1-7):
```

### Example Move
If Player 1 chooses column 4, the disc appears in the bottom row of column 4.

### Example Win Message
```text
Player 1 wins!
Game over! Player 1 wins.
```

### Example Draw Message
```text
It's a draw!
Game over! It's a draw.
```

---

## Troubleshooting

### The game does not start
Make sure you are running:

```bash
python main.py
```

or:

```bash
python3 main.py
```

### I entered a letter and got an error
This is expected behavior. The game asks for a column number only.

### A column says it is full
Choose another column. No more discs can be placed in that column.

### I want to play again
Restart the program by running `python main.py` again.

---

## Notes for Developers

### Core Logic
The main game logic is implemented in `game.py` inside the `ConnectFourGame` dataclass.

Key methods:
- `drop_piece(column)` — places a disc in the selected column
- `check_win(player)` — checks all win conditions
- `is_board_full()` — checks for a draw
- `render_board()` — returns a text representation of the board

### Extending the Game
Possible future improvements:
- Add a graphical interface
- Add a replay feature
- Add AI opponent support
- Add customizable board sizes
- Add colorized terminal output

---

## License

This project is provided as part of an application task and may be adapted as needed for internal use.
```