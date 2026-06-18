# Pong Game User Manual

A simple, fast-paced **two-player Pong game** built with Python and Pygame.

---

## 1. Overview

This application is a classic arcade-style Pong game for **two local players**. Each player controls a vertical paddle and tries to bounce the ball past the opponent’s paddle to score points.

### Main Features

- **Two-player local gameplay**
  - Left player uses **W / S**
  - Right player uses **Up / Down**
- **Ball physics**
  - Ball bounces off:
    - top edge
    - bottom edge
    - paddles
- **Scoring system**
  - A player scores when the opponent misses the ball
- **Winning score threshold**
  - First player to reach the target score wins
- **Automatic ball reset**
  - After each point, the ball resets to the center and serves again after a short delay
- **Restart support**
  - Restart the match after game over by pressing **R**

---

## 2. Requirements

### Software Dependencies

- Python 3.x
- `pygame`

### Included Dependency File

The project includes:

```txt
pygame
```

---

## 3. Installation

Follow these steps to set up the game.

### Step 1: Install Python

Make sure Python is installed on your computer.

You can verify it with:

```bash
python --version
```

or:

```bash
python3 --version
```

### Step 2: Install Dependencies

Install the required Python package:

```bash
pip install -r requirements.txt
```

If you prefer installing directly:

```bash
pip install pygame
```

---

## 4. How to Run the Game

After installing dependencies, start the game with:

```bash
python main.py
```

If your system uses `python3`, use:

```bash
python3 main.py
```

---

## 5. Controls

### Left Player
- **W** — move paddle up
- **S** — move paddle down

### Right Player
- **Up Arrow** — move paddle up
- **Down Arrow** — move paddle down

### Game Controls
- **R** — restart after game over
- **ESC** — quit the game
- Close the game window — quit the game

---

## 6. How to Play

1. Launch the game.
2. Wait for the ball to serve from the center.
3. Use your paddle to bounce the ball back.
4. Try to make the opponent miss the ball.
5. Each time the opponent misses:
   - you gain 1 point
   - the ball resets to the center
   - the next serve begins after a short delay
6. The first player to reach the winning score wins the match.

---

## 7. Game Rules

- The ball bounces off the **top** and **bottom** boundaries.
- The ball bounces off paddles when contacted.
- If the ball travels beyond the left edge:
  - the **right player** scores
- If the ball travels beyond the right edge:
  - the **left player** scores
- The match ends when one player reaches the winning score threshold.

---

## 8. Interface Description

The game window includes:

- **Left paddle**
- **Right paddle**
- **Ball**
- **Score display**
- **Winning score indicator**
- **Game-over overlay** when someone wins

### Score Display

The current scores are shown at the top of the screen.

### Winning Threshold

A message displays the target score, for example:

- `First to 10`

### Game Over Screen

When a player wins, the screen shows:
- the winner announcement
- restart instructions

---

## 9. Match Restart

When the game is over, you can restart the full match by pressing:

```bash
R
```

This will:
- reset both scores to 0
- move paddles back to their starting positions
- reset the ball
- start a new match

---

## 10. Troubleshooting

### `ModuleNotFoundError: No module named 'pygame'`

Install pygame:

```bash
pip install pygame
```

or:

```bash
pip install -r requirements.txt
```

### Game window does not open

- Confirm Python is installed correctly
- Ensure your system supports graphical applications
- Try running from a local desktop environment, not a headless server

### Game is too fast or too slow

The current speed is configured in the source code:
- paddle speed
- ball speed
- winning threshold
- serve delay

These values can be adjusted in `game.py`.

---

## 11. Project Files

- `main.py` — application entry point
- `game.py` — main game loop and logic
- `paddle.py` — paddle behavior and rendering
- `ball.py` — ball behavior and rendering
- `requirements.txt` — Python dependencies

---

## 12. Notes for Users

- This is a **local two-player game**; there is no AI opponent.
- Both players share the same keyboard.
- The game is intended to be simple, responsive, and easy to run.

Enjoy the game!