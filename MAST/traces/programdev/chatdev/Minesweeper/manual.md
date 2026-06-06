# Minesweeper Game User Manual

Welcome to the Minesweeper Game! This classic game challenges your strategic thinking and problem-solving skills. This guide will help you understand the main functions of the software, how to install it, and how to play the game.

## Main Functions

The Minesweeper Game is designed with the following features:

- **Three Levels of Difficulty**: Choose from beginner, intermediate, or expert levels to match your skill level.
- **Interactive Gameplay**: Uncover cells by clicking on them. Numbers on uncovered cells indicate how many mines are adjacent.
- **Flagging Mechanism**: Right-click to flag suspected mines, helping you keep track of potential dangers.
- **Game Over and Win Conditions**: If you uncover a mine, the game ends. Successfully uncover all non-mine cells to win.
- **Visual Feedback**: The game board updates visually after each move, with distinct visuals for flagged cells and uncovered mines.

## Installation

### Prerequisites

Ensure you have Python installed on your system. You can download it from [python.org](https://www.python.org/).

### Quick Install

1. **Clone the Repository**: Clone the Minesweeper game repository to your local machine.

   ```bash
   git clone <repository-url>
   ```

2. **Navigate to the Project Directory**: Change into the directory where the game files are located.

   ```bash
   cd <repository-directory>
   ```

3. **Install Dependencies**: The game does not require any additional dependencies beyond Python's standard library.

   ```bash
   pip install -r requirements.txt
   ```

## How to Play

1. **Start the Game**: Run the `main.py` file to start the game.

   ```bash
   python main.py
   ```

2. **Choose Difficulty Level**: The game starts at the beginner level by default. You can change the difficulty level by modifying the `level` variable in the `main.py` file to "intermediate" or "expert".

3. **Gameplay**:
   - **Uncover Cells**: Click on a cell to uncover it. If it contains a mine, the game will end.
   - **Flag Mines**: Right-click on a cell to flag it as a suspected mine. Flagged cells are marked with an "F" and have a yellow background.
   - **Win the Game**: Uncover all non-mine cells to win. If you win, a congratulatory message will appear.

4. **Game Over**: If you uncover a mine, the game will display a "Game Over" message.

Enjoy the challenge and have fun playing Minesweeper! If you have any questions or need further assistance, feel free to reach out.