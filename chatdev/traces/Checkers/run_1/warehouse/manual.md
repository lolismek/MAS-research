```markdown
# Checkers (Draughts) Game Manual

A simple terminal-based Checkers (Draughts) game built in Python.

This application provides:

- An **8x8 checkers board**
- **Two-player alternating turns**
- **Standard movement rules**
- **Capture enforcement**
- **Kinging** when a piece reaches the opposite end
- **Move input in notation format** like `b6-a5`
- **Board updates after each valid move**

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [How to Run](#how-to-run)
- [Game Rules](#game-rules)
- [How to Play](#how-to-play)
- [Move Notation](#move-notation)
- [Board Representation](#board-representation)
- [Commands](#commands)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## Overview

This program implements a playable Checkers game in the terminal.

Players take turns entering moves using chess-like board coordinates, such as:

- `b6-a5`
- `c3-e5`

The game validates each move, applies captures when required, promotes pieces to kings, and detects when the game is over.

---

## Features

### Core Gameplay
- Standard 8x8 board
- Red starts first
- Alternate turns between Red and Black
- Validates legal moves
- Supports diagonal movement
- Supports captures
- Forces captures when available
- Supports multiple capture chains with the same piece
- Promotes pieces to kings upon reaching the far side

### User Interface
- Terminal/command-line interface
- Board printed after every turn
- Clear prompts and error messages
- `help`, `reset`, and `quit` commands

---

## Requirements

- **Python 3.8 or newer** recommended
- No third-party libraries are required

The application uses only Python standard library modules.

---

## Installation

### 1. Download the Project

Make sure the following files are in the same directory:

- `main.py`
- `game.py`
- `gui.py`

### 2. Verify Python Installation

Check your Python version:

```bash
python --version
```

or, on some systems:

```bash
python3 --version
```

### 3. Optional: Create a Virtual Environment

Although this project has no external dependencies, you may still want to use a virtual environment.

#### On Windows
```bash
python -m venv .venv
.venv\Scripts\activate
```

#### On macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## How to Run

From the project directory, run:

```bash
python main.py
```

or:

```bash
python3 main.py
```

The game will launch in the terminal and display the board.

---

## Game Rules

This implementation follows standard checkers behavior with the following rules:

### 1. Board Setup
- The board is 8x8
- Red pieces are placed on the bottom three rows
- Black pieces are placed on the top three rows
- Only dark squares are used for pieces

### 2. Turns
- Players alternate turns
- Red moves first
- You can only move your own pieces on your turn

### 3. Normal Movement
- Regular pieces move diagonally forward by one square
- Red pieces move upward on the board
- Black pieces move downward on the board
- Kings can move diagonally in all four directions

### 4. Capturing
- If an enemy piece is diagonally adjacent and the square beyond it is empty, you may capture it
- Captures are enforced when available
- If a capture is available, a simple move is not allowed

### 5. Multiple Captures
- If a piece captures and can continue capturing from its new position, it must keep capturing with the same piece
- The game will prompt for the forced continuation

### 6. Kinging
- When a Red piece reaches row 8 in notation terms (`a8` through `h8`), it becomes a Red King
- When a Black piece reaches row 1 in notation terms (`a1` through `h1`), it becomes a Black King
- Kings can move and capture diagonally in all directions

### 7. Game End
The game ends when the current player has no legal moves remaining.

---

## How to Play

### Step 1: Start the game
Run the application:

```bash
python main.py
```

### Step 2: Read the board
The board is shown with coordinates:
- Columns: `a` through `h`
- Rows: `8` through `1`

### Step 3: Enter a move
Type a move using the format:

```text
source-destination
```

Example:

```text
b6-a5
```

### Step 4: Wait for validation
The game will:
- Check whether the move is legal
- Apply the move if valid
- Remove captured pieces if necessary
- Promote kings if applicable
- Switch to the other player

### Step 5: Continue until game over
Keep playing until one player has no valid moves left.

---

## Move Notation

Moves use the format:

```text
<source>-<destination>
```

Where each square is described using:

- A column letter from `a` to `h`
- A row number from `1` to `8`

### Examples
- `b6-a5`
- `c3-d4`
- `f6-h4`

### Notes
- The source square must contain one of your pieces
- The destination square must be empty
- Diagonal movement only
- Captures move two squares diagonally over an opponent piece

---

## Board Representation

The board is printed in text form.

### Piece Symbols
- `r` = Red piece
- `R` = Red king
- `b` = Black piece
- `B` = Black king
- `.` = Empty square

### Example Board Layout

```text
   a b c d e f g h
8  . b . b . b . b
7  b . b . b . b .
6  . b . b . b . b
5  . . . . . . . .
4  . . . . . . . .
3  r . r . r . r .
2  . r . r . r . r
1  r . r . r . r .
```

---

## Commands

In addition to move input, the following commands are available:

### `help`
Displays the list of commands and basic usage instructions.

### `reset`
Restarts the game from the initial starting position.

### `quit`
Exits the game.

---

## Examples

### Example 1: Simple Move
If it is Red's turn, a valid move might be:

```text
b6-a5
```

This moves a Red piece diagonally forward one square.

### Example 2: Capture Move
If a capture is available, a move like this may be required:

```text
c3-e5
```

This jumps over an enemy piece and removes it from the board.

### Example 3: King Promotion
If a Red piece reaches the top row of the board, it becomes:

```text
R
```

If a Black piece reaches the bottom row, it becomes:

```text
B
```

### Example 4: Forced Multi-Capture
If the same piece can capture again after a jump, the game will require you to continue using that piece.

You will see a message like:

```text
Forced capture continuation from e5
```

Then you must enter the next capture move from that same square.

---

## Troubleshooting

### "Move must use '-' notation"
Your input must use the format:

```text
b6-a5
```

not:

```text
b6 a5
```

or:

```text
b6toa5
```

### "No piece at source square"
There is no piece on the selected source square.

### "It is not that piece's turn"
You tried to move the opponent’s piece.

### "Destination square is not empty"
The target square already contains a piece.

### "A capture is available and must be taken"
You attempted a simple move while a capture was available. You must capture instead.

### "You must continue capturing with the same piece"
A multi-capture sequence is active, and you must keep capturing with that same piece.

### Game exits immediately
If the program is run in a non-interactive environment and no input is available, it may exit cleanly after printing the board.

---

## Summary

This Checkers game is a terminal-based Python application that allows two players to play standard draughts on an 8x8 board using move notation like `b6-a5`.

Enjoy playing!
```