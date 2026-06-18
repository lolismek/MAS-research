# Simplified Monopoly Go! User Manual

## Overview

**Simplified Monopoly Go!** is a Python-based board game application inspired by Monopoly-style gameplay.  
It supports both:

- **Tkinter GUI mode** for a windowed experience
- **Console mode** as a fallback when Tkinter is unavailable

The game includes the core mechanics requested by the customer:

- Rolling dice
- Moving around a board
- Landing on properties
- Buying unowned properties
- Paying rent to property owners
- Chance cards with simplified effects
- Jail rules
- Free Parking spaces
- Money tracking and property ownership
- Turn-by-turn prompts and game status display

---

## Main Features

### 1. Dice Rolling
Each turn, a player rolls **two six-sided dice**. The total determines how many spaces the player moves.

### 2. Board Movement
Players move around a simplified board containing:

- GO
- Property spaces
- Chance spaces
- Jail
- Free Parking
- Go To Jail

Passing GO grants the player **$200**.

### 3. Properties
When a player lands on an **unowned property**, they may choose to buy it if they have enough money.

If the property is already owned by another player, the current player must pay rent.

### 4. Money and Ownership Tracking
The game tracks:

- Each player’s cash balance
- Which properties each player owns
- Bankruptcy status

### 5. Chance Cards
Landing on a Chance space triggers a random card, such as:

- Collect $50
- Pay $50
- Advance to GO
- Go to Jail
- Collect money from each player
- Pay each player

### 6. Jail Rules
If a player is sent to jail:

- Their token moves to the Jail space
- They skip turns while in jail
- After 3 turns, they are automatically released

### 7. Free Parking
Free Parking is a rest space.  
Nothing happens when a player lands there.

### 8. Win Condition
The game ends when only one active player remains.  
That player is declared the winner.

---

## Installation

## Requirements

- **Python 3.9+** recommended
- No external third-party packages are required
- **Tkinter** is optional but recommended for GUI mode

### Tkinter Notes
- On many systems, Tkinter is included with Python
- If Tkinter is unavailable, the program automatically falls back to **console mode**

---

## How to Run

### Option 1: GUI Mode
Run the main entry point:

```bash
python main.py
```

If Tkinter is available, a window will open.

### Option 2: Console Mode
If Tkinter is not available, the game will automatically start in console mode.

You can also run it the same way:

```bash
python main.py
```

---

## Project Files

### `main.py`
The application entry point.  
It starts the game and launches the GUI or console interface.

### `game.py`
Contains the core game logic:

- turn handling
- movement
- rent and purchase logic
- jail and bankruptcy rules
- winner detection

### `models.py`
Defines the game data models:

- `Player`
- `Property`
- `Space`
- `ChanceCard`

### `board.py`
Creates the board layout used by the game.

### `chance.py`
Defines the simplified Chance card deck and random drawing behavior.

### `ui.py`
Contains:

- Tkinter GUI implementation
- Console fallback interface

---

## How to Play

## 1. Start the Game
Launch the app with:

```bash
python main.py
```

Then enter player names separated by commas.

Example:

```text
Alice, Bob, Charlie
```

At least **2 players** are required.

---

## 2. Start of Turn
At the beginning of each turn, the game tells you whose turn it is.

You will be prompted to:

- roll
- buy
- skip
- end
- view status
- quit

---

## 3. Roll the Dice
Choose:

```text
roll
```

The game will:

- roll two dice
- move your token
- resolve the space you landed on

---

## 4. Buy a Property
If you land on an unowned property, you may buy it.

Choose:

```text
buy
```

If you have enough money:

- the purchase succeeds
- the property becomes yours
- the cost is deducted from your money

If you do not have enough money:

- you go bankrupt
- your turn ends

---

## 5. Skip Buying
If you do not want to buy a property, choose:

```text
skip
```

This keeps the property unowned.

---

## 6. End Your Turn
When your actions are complete, choose:

```text
end
```

The turn advances to the next active player.

---

## 7. View Status
Choose:

```text
status
```

This shows each player’s:

- money
- position
- jail status
- active/bankrupt status
- properties owned

---

## 8. Quit the Game
Choose:

```text
quit
```

This exits the application.

---

## Game Rules Explained

## GO
- Passing GO gives you **$200**
- Landing directly on GO has no extra effect

## Properties
- Unowned property: may be purchased
- Owned by another player: pay rent
- Owned by yourself: no rent is paid

## Rent
Rent is automatically transferred to the property owner when another player lands on their property.

## Chance
Landing on Chance triggers one random chance card.

## Jail
A player may be sent to jail by:

- Landing on “Go To Jail”
- Drawing a “Go to Jail” chance card

While in jail:

- The player skips their turn
- After 3 skipped turns, they are released automatically

## Free Parking
No action occurs.

## Bankruptcy
A player becomes bankrupt when they cannot continue financially.

When bankruptcy occurs:

- the player becomes inactive
- their properties are transferred to the creditor if applicable
- otherwise, properties return to the bank

## Winning the Game
The last active player wins.

---

## GUI Controls

If Tkinter is available, the game window includes:

- **Roll Dice**: roll and move
- **Buy Property**: buy the current unowned property
- **Skip Buy**: decline purchase
- **End Turn**: finish turn and pass to the next player

The GUI also displays:

- board state
- player status
- game log

---

## Console Controls

If the program runs in console mode, use these commands:

- `roll`
- `buy`
- `skip`
- `end`
- `status`
- `quit`

---

## Example Gameplay Flow

1. Start game
2. Player A rolls dice
3. Player A lands on an unowned property
4. Player A buys the property
5. Player A ends turn
6. Player B rolls dice
7. Player B lands on Player A’s property
8. Player B pays rent
9. Player B ends turn
10. A chance card sends a player to jail
11. Game continues until one player remains

---

## Troubleshooting

### The GUI does not open
This usually means Tkinter is unavailable in your Python installation.

**Solution:**  
The game will automatically use console mode.

### I cannot type input in console mode
Console mode requires a terminal or command-line environment.

**Solution:**  
Run the script in a real terminal, not in a non-interactive environment.

### The game says at least 2 players are required
You must enter at least two valid player names.

Example:

```text
Alice, Bob
```

### The game ends unexpectedly
A player may have gone bankrupt, leaving only one active player.

---

## Notes

This is a **simplified** Monopoly Go-style implementation.  
It does **not** include all official Monopoly rules or all Monopoly Go features.  
It focuses on the essential mechanics requested:

- movement
- property ownership
- rent
- chance
- jail
- free parking
- player money tracking

---

## Quick Start Summary

```bash
python main.py
```

Then:

1. Enter player names
2. Roll dice
3. Buy properties or skip
4. Pay rent when required
5. Handle chance and jail events
6. Continue until one player wins

---

If you want, I can also generate a **README.md** version of this manual or a **shorter end-user guide** for the game UI.