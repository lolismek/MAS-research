# Match-3 Puzzle Game User Manual

A classic **match-3 puzzle game** inspired by Candy Crush, built with **Python** and **Tkinter**.

Match candies by swapping adjacent tiles to create horizontal or vertical lines of **3 or more** identical candies. Matched candies disappear, candies above fall down, new candies fill the board, and your score increases. Chain reactions are supported automatically.

---

## Table of Contents

- [What This Game Does](#what-this-game-does)
- [Main Features](#main-features)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [How to Run](#how-to-run)
- [How to Play](#how-to-play)
- [Game Rules](#game-rules)
- [Scoring and Progress](#scoring-and-progress)
- [Game Over Conditions](#game-over-conditions)
- [Troubleshooting](#troubleshooting)

---

## What This Game Does

This application is a board-based puzzle game where you:

1. Select one candy.
2. Select an adjacent candy to swap with.
3. If the swap creates a match of 3 or more, the candies are cleared.
4. Candies above fall down.
5. New candies appear at the top.
6. If falling candies create new matches, those are cleared too, causing **chain reactions**.
7. Your score is updated after each valid move.

---

## Main Features

- **8×8 game board**
- **6 candy types**
- **Mouse click interaction**
- **Adjacent swap validation**
- **Match detection** for horizontal and vertical lines
- **Automatic clearing** of matched candies
- **Gravity/collapse mechanic** so candies fall after clearing
- **Board refill** with new random candies
- **Score tracking**
- **Move limit**
- **Target score win condition**
- **Game over screen**
- **Fallback support** if Tkinter GUI is unavailable

---

## Project Structure

The project contains these files:

- `main.py`  
  Application entry point.

- `game_controller.py`  
  Controls game flow, scoring, move counts, and interaction between board and UI.

- `board.py`  
  Contains the core match-3 game logic:
  - board generation
  - swap logic
  - match detection
  - clearing
  - falling/collapse
  - refill
  - cascade resolution

- `game_ui.py`  
  Tkinter graphical interface for displaying the board and handling clicks.

---

## Requirements

### Software Requirements

- **Python 3.9+** recommended
- Standard library only
- Optional: **Tkinter**
  - Tkinter is usually included with Python on Windows and macOS
  - On some Linux systems, it may need to be installed separately

### No external Python packages are required

This project uses only Python’s built-in modules:

- `random`
- `dataclasses`
- `typing`
- `tkinter` (optional, for GUI)

---

## Installation

### 1. Download the project

Clone or copy the project files into a local directory.

Example:

```bash
git clone <repository-url>
cd <project-directory>
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
```

Activate it:

#### Windows
```bash
venv\Scripts\activate
```

#### macOS / Linux
```bash
source venv/bin/activate
```

### 3. Install dependencies

There are no third-party dependencies to install.

If Tkinter is missing on Linux, install it using your system package manager:

#### Ubuntu / Debian
```bash
sudo apt-get update
sudo apt-get install python3-tk
```

#### Fedora
```bash
sudo dnf install python3-tkinter
```

#### Arch Linux
```bash
sudo pacman -S tk
```

---

## How to Run

Run the application from the project root:

```bash
python main.py
```

If your system uses `python3`, you can run:

```bash
python3 main.py
```

If Tkinter is available, a game window will open.

If Tkinter is not available, the program will start in fallback mode and print a message indicating that the GUI cannot be displayed.

---

## How to Play

### Step 1: Start the game

Launch `main.py`. The board will appear with colorful candies.

### Step 2: Select a candy

Click any candy on the board.

- The selected candy will be highlighted with a bold outline.

### Step 3: Select an adjacent candy

Click a candy next to the selected one.

- Only swaps between **adjacent** candies are allowed.
- Adjacent means:
  - one cell up
  - one cell down
  - one cell left
  - one cell right

### Step 4: Check the result

If the swap creates a match:

- The matched candies are cleared
- Candies fall downward
- Empty spaces are filled with new candies
- Additional matches caused by falling are automatically cleared
- Your score increases

If the swap does **not** create a match:

- The swap is undone
- A status message says the move was invalid

---

## Game Rules

### Match Rule

A match occurs when **3 or more identical candies** are aligned:

- horizontally
- vertically

### Valid Move Rule

A move is valid only if swapping two adjacent candies immediately creates at least one match.

### Chain Reaction Rule

After matches are cleared:

- remaining candies fall due to gravity
- new candies appear at the top
- this may create more matches
- the game continues resolving until the board becomes stable

### Move Limit Rule

The game includes a limited number of moves.

- Default: **30 moves**
- Each successful move consumes 1 move

### Win Condition

You win by reaching the target score.

- Default target score: **2000**

### Lose Conditions

You lose if:

- you run out of moves
- no valid moves remain on the board

---

## Scoring and Progress

### Score Tracking

The HUD shows:

- **Score**
- **Moves Left**
- **Target**

### How scoring works

Whenever a valid swap triggers clearing:

- each cleared candy contributes to the total gained score metric
- chain reactions also count toward the total cleared candies

The game uses the number of candies cleared to update the score.

### Example

If one move triggers:

- 3 candies cleared initially
- 6 more candies cleared in cascades

Then the total gained is based on all cleared candies in that move.

---

## Game Over Conditions

When the game ends, a game-over overlay appears with a message such as:

- `You reached the target score. You win!`
- `No moves left. Game over!`
- `No valid moves remain. Game over!`

If running without Tkinter, the message will be printed in the console.

---

## Troubleshooting

### The game window does not open

Possible causes:

- Tkinter is not installed
- Python was built without Tk support
- You are running in a headless environment without a display

Try installing Tkinter for your operating system.

### The game starts but nothing appears

Make sure you are running:

```bash
python main.py
```

from the correct project directory.

### Clicks do not seem to work

Remember:

- first click selects a candy
- second click must be on an adjacent candy
- a swap must create a match to be valid

### I get an import error for Tkinter on Linux

Install the Tk package:

```bash
sudo apt-get install python3-tk
```

---

## Notes for Users

- The game board is generated randomly each time you start a new game.
- The board is automatically initialized without starting matches.
- The interface is designed for simple mouse-based play.
- All core game logic is self-contained in the Python source files.

---

## Summary

This match-3 puzzle game offers a simple, interactive candy-matching experience with:

- clickable board interaction
- match detection
- cascading clears
- scoring
- move limits
- win/lose conditions

Enjoy playing and trying to reach the target score before your moves run out!