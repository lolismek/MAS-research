```markdown
# Tetris Game

Welcome to the Tetris Game, a classic puzzle game where you strategically place falling Tetrominoes to clear lines and score points. This guide will help you install, set up, and play the game.

## Quick Install

To get started with the Tetris Game, you need to install the required dependencies. The game is built using Python and the Pygame library.

### Prerequisites

- Python 3.x installed on your system. You can download it from [python.org](https://www.python.org/downloads/).

### Installation Steps

1. **Clone the Repository**

   First, clone the repository to your local machine using the following command:

   ```bash
   git clone <repository-url>
   ```

   Replace `<repository-url>` with the actual URL of the repository.

2. **Navigate to the Project Directory**

   Change your directory to the project folder:

   ```bash
   cd <project-directory>
   ```

   Replace `<project-directory>` with the name of the cloned directory.

3. **Install Dependencies**

   Install the required dependencies using pip:

   ```bash
   pip install -r requirements.txt
   ```

   This will install the Pygame library necessary to run the game.

## 🤔 What is this?

The Tetris Game is a digital version of the classic Tetris puzzle game. The objective is to manipulate falling Tetrominoes by moving them sideways and rotating them to create a horizontal line of blocks without gaps. When such a line is created, it disappears, and any block above the deleted line will fall. The game ends when there is no room for new Tetrominoes to fall.

### Main Features

- **Seven Standard Tetromino Shapes**: Includes I, T, S, Z, O, L, and J shapes.
- **Increasing Difficulty**: The drop speed of Tetrominoes increases as you score more points.
- **Score Tracking**: Earn points by clearing lines.
- **Game Over Detection**: The game ends when no more pieces can be placed.

## 📖 How to Play

1. **Start the Game**

   Run the main script to start the game:

   ```bash
   python main.py
   ```

2. **Game Controls**

   - **Left Arrow Key**: Move the current Tetromino left.
   - **Right Arrow Key**: Move the current Tetromino right.
   - **Down Arrow Key**: Move the current Tetromino down faster.
   - **Up Arrow Key**: Rotate the current Tetromino.

3. **Objective**

   - Arrange the falling Tetrominoes to form complete horizontal lines.
   - Each completed line will disappear, and you will earn points.
   - The game ends when the Tetrominoes stack up to the top of the board.

4. **Scoring**

   - You earn 100 points for each line cleared.
   - The drop speed increases as your score increases, making the game more challenging.

## 📖 Documentation

For more detailed information about the game's architecture and code, please refer to the source code files:

- `main.py`: Entry point for the game.
- `game.py`: Manages the game loop and user input.
- `board.py`: Handles the Tetris board and line clearing.
- `tetromino.py`: Manages Tetromino shapes and movements.
- `score.py`: Manages the scoring system.
- `constants.py`: Defines game constants.

Enjoy the game and aim for the highest score!
```