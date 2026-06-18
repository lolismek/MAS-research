```markdown
# Simplified Space Invaders

A lightweight Python arcade game inspired by the classic **Space Invaders**.  
Control your ship at the bottom of the screen, shoot descending alien rows, and survive as long as you can.

## Features

- Smooth horizontal player movement
- Player firing with a short cooldown
- Multiple alien rows and columns
- Alien formation movement with edge bouncing and downward descent
- Limited lives
- Score tracking
- Win condition when all aliens are destroyed
- Game over when aliens reach the bottom danger line or the player loses all lives
- Restart support after victory or defeat

---

## Requirements

- Python 3.9 or newer recommended
- `pygame`

---

## Installation

### 1) Clone or download the project
Make sure the project files are in one folder, for example:

```text
main.py
game.py
entities.py
settings.py
requirements.txt
```

### 2) Install dependencies

Using `pip`:

```bash
pip install -r requirements.txt
```

If you prefer installing directly:

```bash
pip install pygame
```

> If `pygame` is not installed, the game will show a clear error message telling you to install it.

---

## How to Run

Run the entry point:

```bash
python main.py
```

This will open the game window and start the alien invasion immediately.

---

## Game Objective

Your mission is simple:

- Destroy all alien ships
- Avoid letting aliens reach the bottom danger line
- Avoid direct contact with aliens
- Keep your remaining lives alive for as long as possible

You win by eliminating every alien in the fleet.  
You lose if all lives are gone or the aliens advance too far downward.

---

## Controls

### Movement
- **Left Arrow** or **A**: Move ship left
- **Right Arrow** or **D**: Move ship right

### Shooting
- **Spacebar**: Fire a bullet

### Restart
- **R**: Restart the game after a win or loss

### Quit
- Close the window using the standard window close button

---

## Gameplay Rules

### Player
- You control a ship at the bottom of the screen.
- The ship can only move horizontally.
- Firing is limited by a short cooldown, so you cannot shoot continuously without pause.

### Bullets
- Bullets move upward.
- A bullet disappears when it leaves the screen or hits an alien.
- Each bullet can destroy one alien.

### Aliens
- Aliens are arranged in a grid of multiple rows and columns.
- The alien formation moves horizontally across the screen.
- When the formation hits the edge, it reverses direction and drops down.
- As aliens descend, the danger increases.

### Lives
- You begin with a limited number of lives.
- If an alien touches your ship, you lose a life.
- If an alien reaches the bottom danger line, you also lose a life.
- After losing a life, the game briefly pauses and resets the player for the next wave.

### Score
- Destroying one alien awards points.
- The score is shown in the top-left corner during play.

---

## User Interface

During gameplay, the HUD displays:

- **Score**: Your current points
- **Lives**: Remaining lives
- **Aliens**: Number of aliens still alive

When a life is lost, a short message appears:

- “Life lost! Prepare for the next wave...”

When the game ends, an overlay appears showing:

- **YOU WIN!** if all aliens are defeated
- **GAME OVER** if you lose all lives or the aliens get too close

The overlay also shows a restart prompt.

---

## Tips for Playing

- Move early to align shots with alien rows.
- Try to shoot from under the edge of the formation as it bounces.
- Avoid staying under descending aliens for too long.
- Use the pause after losing a life to reposition carefully.

---

## Troubleshooting

### `ModuleNotFoundError: pygame`
Install pygame with:

```bash
pip install pygame
```

### Game window does not open
Make sure:

- You are running the correct Python interpreter
- `pygame` installed successfully
- Your environment supports graphical applications

### Controls do not respond
Click the game window to ensure it is focused, then try again.

---

## File Overview

- **main.py**  
  Entry point that starts the game.

- **game.py**  
  Contains the main game loop, event handling, scoring, win/loss logic, and rendering.

- **entities.py**  
  Defines the player ship, bullets, and alien entities.

- **settings.py**  
  Holds all game constants such as screen size, speed, colors, and gameplay values.

- **requirements.txt**  
  Lists Python dependencies.

---

## Notes

This is a simplified version of Space Invaders designed to be easy to run and understand.  
It is a single-player arcade game with a clean structure and minimal dependencies.

Enjoy defending Earth!
```