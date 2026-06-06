# Puzzle Game User Manual

Welcome to the Puzzle Game! This manual will guide you through the installation, setup, and gameplay of our engaging word puzzle game. The game challenges players to group words into categories, providing a fun and educational experience.

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Game Features](#game-features)
4. [How to Play](#how-to-play)
5. [Daily Puzzle](#daily-puzzle)
6. [Troubleshooting](#troubleshooting)

## Introduction

The Puzzle Game is a word-based puzzle application where players must group 16 words into four sets of four, based on hidden categories. The words are presented in a 4x4 grid, and players select four at a time to form a group. Correct groups are removed and revealed with a category and a color-coded difficulty. Incorrect guesses count as mistakes, with a maximum of four allowed. A new puzzle is generated daily, ensuring a fresh challenge every day.

## Installation

To install and run the Puzzle Game, follow these steps:

1. **Ensure Python is Installed**: Make sure you have Python 3.x installed on your system. You can download it from [python.org](https://www.python.org/downloads/).

2. **Clone the Repository**: Clone the game repository from the source.

   ```bash
   git clone <repository-url>
   ```

3. **Navigate to the Project Directory**: 

   ```bash
   cd <repository-directory>
   ```

4. **Install Dependencies**: Install the required Python packages using pip.

   ```bash
   pip install -r requirements.txt
   ```

   If a `requirements.txt` file is not provided, you may need to manually install packages like `tkinter` and any other dependencies mentioned in the code.

## Game Features

- **4x4 Word Grid**: Words are displayed in a 4x4 grid for easy selection.
- **Category Grouping**: Group words into categories such as fruits, animals, colors, and vehicles.
- **Color-Coded Feedback**: Correct groups are highlighted with color-coded difficulty levels.
- **Mistake Tracking**: Players can make up to four mistakes before the game ends.
- **Daily Puzzle**: A new puzzle is generated every day, providing continuous engagement.

## How to Play

1. **Start the Game**: Run the main application file to start the game.

   ```bash
   python main.py
   ```

2. **Select Words**: Click on words in the grid to select them. Select four words to form a group.

3. **Check Group**: Once four words are selected, the game will automatically check if they form a correct group.

4. **Feedback**: Receive immediate feedback. Correct groups are removed and revealed with their category and color. Incorrect guesses increase the mistake count.

5. **Game Over**: The game ends if you make four mistakes.

6. **Reset Game**: Use the reset button to start a new game with a fresh puzzle.

## Daily Puzzle

The game features a daily puzzle that changes every day. This ensures that players have a new challenge to look forward to each day. The daily puzzle is generated based on the current date, providing a unique puzzle experience.

## Troubleshooting

- **Game Not Starting**: Ensure all dependencies are installed and that Python is correctly set up on your system.
- **GUI Issues**: If the GUI does not display correctly, check your Python installation and ensure `tkinter` is installed.
- **Puzzle Not Loading**: Verify that the `daily_puzzle.py` file is correctly loading puzzles and that the date-based logic is functioning.

For further assistance, please contact our support team or refer to the documentation provided in the source code. Enjoy the Puzzle Game and challenge your word grouping skills!