```markdown
# Space Invaders Game

A simplified version of the classic Space Invaders game where the player controls a ship at the bottom of the screen, moving horizontally and firing shots to destroy descending alien rows. The game ends if aliens reach the bottom or the player defeats all aliens. The game includes multiple alien rows, a limited number of lives, and score tracking.

## Quick Install

To run the Space Invaders game, you need to have Python and Pygame installed on your system. Follow the steps below to set up the environment and start the game:

### Step 1: Install Python

Ensure that you have Python installed on your system. You can download it from [python.org](https://www.python.org/downloads/).

### Step 2: Install Pygame

Once Python is installed, you can install Pygame using pip. Open your terminal or command prompt and run the following command:

```bash
pip install pygame==2.1.2
```

### Step 3: Download the Game Files

Download the game files and ensure they are in the same directory. The files include:

- `main.py`
- `settings.py`
- `ship.py`
- `alien.py`
- `bullet.py`
- `scoreboard.py`
- `gameover.py` (if applicable)
- `requirements.txt`

Ensure you also have the image files `ship.bmp` and `alien.bmp` in the same directory for the game graphics.

## How to Play

### Starting the Game

1. Navigate to the directory containing the game files in your terminal or command prompt.
2. Run the game by executing the following command:

```bash
python main.py
```

### Game Controls

- **Move Right:** Press the right arrow key to move the ship to the right.
- **Move Left:** Press the left arrow key to move the ship to the left.
- **Fire Bullet:** Press the spacebar to fire a bullet.
- **Restart Game:** Press the 'R' key to restart the game after a game over.

### Game Objective

- **Destroy Aliens:** Use your ship to fire bullets and destroy all the aliens before they reach the bottom of the screen.
- **Score Points:** Earn points by destroying aliens. The score is displayed at the top right corner of the screen.
- **Survive:** You have a limited number of lives. The game ends if you lose all your lives or if the aliens reach the bottom of the screen.

### Game Over

- If the aliens reach the bottom or you lose all your lives, the game will display a "You Lost!" message.
- Press 'R' to restart the game and try again.

## Documentation

For more detailed information on the game's code and structure, refer to the comments within each Python file. Each class and method is documented to help you understand the functionality and flow of the game.

Enjoy playing Space Invaders and aim for the highest score!
```