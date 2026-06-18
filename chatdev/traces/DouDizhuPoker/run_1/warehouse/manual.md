```markdown
# Dou Dizhu (Chinese Poker) Game

A Tkinter-based Dou Dizhu game for three players, featuring:

- 3-player gameplay
- Landlord bidding phase
- Valid combination recognition
- Pass-or-beat turn logic
- Simple AI opponents
- Human-vs-AI play in a desktop GUI
- Console fallback when Tkinter is unavailable

---

## 1. Overview

This software implements the classic **Dou Dizhu** card game, also known as **Chinese Poker** or **Fight the Landlord**.

### Game Objective
- One player becomes the **landlord**
- The landlord receives the 3 bottom cards and plays against the other two players
- The landlord wins by being the first to play all cards
- The two farmers win if they prevent the landlord from emptying their hand first

---

## 2. Main Features

### 2.1 Landlord Bidding
The game includes a bidding phase:
- Players bid in turn
- Bid values range from `0` to `3`
  - `0` = pass
  - `1`, `2`, `3` = bid strength
- The highest bidder becomes the landlord
- If a player bids `3`, the landlord is finalized immediately
- If all players pass, bidding can restart

### 2.2 Valid Dou Dizhu Combinations
The game validates and compares common Dou Dizhu combinations, including:

- Single
- Pair
- Triple
- Straight
- Pair straight
- Triple straight
- Triple with single
- Triple with pair
- Bomb
- Rocket

### 2.3 Pass-or-Beat Logic
After a combination is played:
- The next player must either:
  - play a valid stronger combination, or
  - pass
- If two players pass after a play, the round resets
- The last player to successfully play then starts the next round

### 2.4 AI Players
The software includes simple AI logic for:
- Bidding
- Playing cards
- Choosing whether to pass

### 2.5 GUI and Console Fallback
- If Tkinter is available, the game runs in a graphical interface
- If Tkinter is unavailable, the program automatically switches to a minimal console demonstration mode

---

## 3. Project Structure

Typical files in the project:

- `main.py` — main entry point and GUI/console launcher
- `game_app.py` — Tkinter GUI application
- `game_state.py` — core game state and rule handling
- `combination.py` — combination parsing and comparison
- `cards.py` — card model and deck utilities
- `ai_player.py` — simple AI bidding and play decisions

---

## 4. Installation

## 4.1 Requirements
- Python 3.9 or newer recommended
- Tkinter installed for the GUI version

### Check Python version
```bash
python --version
```

or

```bash
python3 --version
```

---

## 4.2 Optional GUI Dependency: Tkinter

Tkinter is included with many standard Python distributions.

### On Windows
Tkinter is usually included by default.

### On macOS
Tkinter is often bundled with Python from python.org, but may not be available in some system Python installations.

### On Linux
You may need to install it manually.

#### Ubuntu/Debian
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

## 4.3 No Third-Party Dependencies
This project uses only Python standard library modules:
- `random`
- `dataclasses`
- `enum`
- `collections`
- `typing`
- `tkinter`

So no `pip install` is required for the core game.

---

## 5. How to Run

### 5.1 Run the GUI version
From the project directory:

```bash
python main.py
```

If your environment supports Tkinter, the graphical game window will open.

### 5.2 Run the console fallback
If Tkinter is unavailable, the app automatically runs a console-based demonstration.

You do not need to change anything:
```bash
python main.py
```

---

## 6. Gameplay Instructions

## 6.1 Starting a New Game
When the app starts:
- A new game is automatically created
- Cards are shuffled and dealt
- Bidding begins immediately

You can also click:

- **New Game**

to restart at any time.

---

## 6.2 Bidding Phase
During bidding:
- The active player is shown in the UI
- Human player buttons:
  - `Pass`
  - `Bid 1`
  - `Bid 2`
  - `Bid 3`

### Bidding rules:
- Players bid in order
- Higher bids are stronger
- The highest bidder becomes the landlord
- If someone bids `3`, bidding ends immediately
- The landlord receives 3 extra bottom cards

---

## 6.3 Playing Cards
Once bidding ends:
- The landlord starts the first turn
- Players take turns clockwise

### To play cards as the human player:
1. Click one or more cards in your hand to select them
2. Click **Play Selected**
3. If the selected cards form a legal combination and can beat the current table play, they will be played

Selected cards are highlighted.

---

## 6.4 Passing
If a player does not want or cannot beat the current play:
- Click **Pass**

Passing is only allowed when:
- It is your turn
- There is already a current table play to beat

---

## 6.5 Ending a Round
If two consecutive players pass after a valid play:
- The round resets
- The last player who played a valid combination starts the next round

---

## 6.6 Winning the Game
The game ends when a player has no cards left.

- If the landlord empties their hand first, the landlord wins
- If a farmer empties their hand first, the farmers win

The UI will show the winner and whether they were the landlord or a farmer.

---

## 7. Supported Card Combinations

The game recognizes the following standard combinations.

### 7.1 Single
One card.

Example:
- `A♠`

### 7.2 Pair
Two cards of the same rank.

Example:
- `7♦ 7♣`

### 7.3 Triple
Three cards of the same rank.

Example:
- `Q♠ Q♥ Q♦`

### 7.4 Straight
Five or more consecutive singles.
- Cannot contain `2`, `SJ`, or `BJ`

Example:
- `3♠ 4♥ 5♦ 6♣ 7♠`

### 7.5 Pair Straight
Three or more consecutive pairs.
- Cannot contain `2`, `SJ`, or `BJ`

Example:
- `4♠ 4♥ 5♠ 5♥ 6♠ 6♥`

### 7.6 Triple Straight
Two or more consecutive triples.
- Cannot contain `2`, `SJ`, or `BJ`

Example:
- `6♠ 6♥ 6♦ 7♠ 7♥ 7♦`

### 7.7 Triple with Single
A triple plus one extra single.

Example:
- `9♠ 9♥ 9♦ J♣`

### 7.8 Triple with Pair
A triple plus one pair.

Example:
- `K♠ K♥ K♦ 3♣ 3♦`

### 7.9 Bomb
Four cards of the same rank.

Example:
- `8♠ 8♥ 8♦ 8♣`

### 7.10 Rocket
The pair of jokers:
- `SJ`
- `BJ`

This is the strongest possible combination.

---

## 8. Combination Comparison Rules

### General Rules
- A play must usually match the same combination type as the current table play
- It must also be stronger by rank
- Straight-type combinations must match in length

### Special Rules
- **Rocket** beats everything
- **Bomb** beats any non-bomb combination
- A stronger bomb beats a weaker bomb
- Non-bomb combinations cannot beat bombs
- Different combination types cannot normally beat each other

---

## 9. User Interface Guide

The GUI contains the following main areas:

### 9.1 Status Text
Shows:
- Current bidding or turn state
- Current player
- Game over status

### 9.2 Last Play Display
Shows:
- The most recently played combination
- The exact cards in that combination

### 9.3 Landlord Display
Shows:
- Which player is the landlord
- Or “not decided yet” during bidding

### 9.4 Human Hand
Displays your cards as clickable buttons.

### 9.5 Action Buttons
- **Pass** — skip your turn if allowed
- **Play Selected** — play selected cards
- **New Game** — restart the game

### 9.6 Bidding Buttons
- **Pass**
- **Bid 1**
- **Bid 2**
- **Bid 3**

These are active only during bidding and only when it is the human player’s bid turn.

---

## 10. Example Play Flow

1. Start the app
2. Bidding begins
3. Players bid until the landlord is decided
4. The landlord receives the 3 bottom cards
5. The landlord starts the first trick
6. Players alternate between:
   - playing a valid stronger combination, or
   - passing
7. When two players pass, the trick resets
8. The first player to empty their hand wins

---

## 11. Console Demo Mode

If Tkinter is not available, the program uses a minimal console mode.

It will:
- shuffle and deal cards
- run bidding automatically
- print the landlord
- print players’ hands
- let AI players continue until someone wins

This mode is mainly for:
- testing
- headless environments
- systems without GUI support

---

## 12. Notes and Limitations

This implementation focuses on core Dou Dizhu rules and may not cover every advanced regional variation.

### Supported
- Standard 3-player landlord format
- Core combination types
- Bidding phase
- Pass/beat logic
- Basic AI

### Not fully covered
- Every possible advanced attachment variant
- Sophisticated AI strategy
- Ranked online matchmaking
- Multiplayer network play
- Custom rule sets

---

## 13. Troubleshooting

### Tkinter window does not open
Possible causes:
- Tkinter is not installed
- You are using a headless environment
- Your Python distribution lacks GUI support

Fix:
- Install Tkinter for your OS
- Or run in console mode

### “Invalid Move” error
This means the selected cards:
- do not form a valid combination, or
- cannot beat the current play, or
- are not played during your turn

### Cards do not respond
Check whether:
- it is your turn
- bidding has finished
- the game is over

---

## 14. Development Summary

This project is organized around:
- **Game state management**
- **Combination validation**
- **AI decision-making**
- **User interface interaction**

The design separates:
- card logic
- rule logic
- UI logic
- AI logic

This makes the application easier to maintain and extend.

---

## 15. Quick Start

```bash
python main.py
```

Then:
1. Bid for landlord
2. Wait for landlord determination
3. Select cards
4. Play or pass
5. Try to empty your hand first

Enjoy playing Dou Dizhu!
```