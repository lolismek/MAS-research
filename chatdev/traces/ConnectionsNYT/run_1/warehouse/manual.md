```markdown
# Daily Word Group Puzzle — User Manual

## Overview

**Daily Word Group Puzzle** is a Python-based word association game inspired by daily category-grid puzzles.

Your goal is to sort **16 words** into **four hidden groups of four** based on a shared category. The words are shown in a **4×4 grid**, and you must select **exactly four words** at a time to submit a guess.

### Game Features

- **16 words in a 4×4 grid**
- **Group words into four hidden categories**
- **Four difficulty colors**
  - Yellow
  - Green
  - Blue
  - Purple
- **Immediate feedback** after every selection and submission
- **Shuffle** button to rearrange the board
- **Maximum of four mistakes**
- **Only one valid solution**
- **Daily puzzle generation** based on the current date

---

## How the Game Works

Each puzzle contains:

- **16 unique words**
- **4 correct groups**
- **4 words per group**
- **1 category per group**
- **1 difficulty color per group**

When you correctly identify a group:

- The group is removed from the active board
- The category is revealed
- The group is shown with its difficulty color

If your guess is wrong:

- A mistake is recorded
- You can make up to **4 mistakes**
- After the fourth mistake, the game ends

---

## Requirements

### Software Requirements

- **Python 3.10+ recommended**
- **Tkinter GUI support**
  - Tkinter is usually included with standard Python installations
  - On some Linux systems, you may need to install it separately

### Optional / Platform Notes

If Tkinter is unavailable, the application will fall back to a text message explaining that the GUI cannot be started.

---

## Installation

### 1. Download the Project

Make sure the following files are present in the same directory:

- `main.py`
- `puzzle_data.py`
- `game_logic.py`
- `ui.py`

### 2. Create a Virtual Environment (Recommended)

```bash
python -m venv .venv
```

Activate it:

#### Windows
```bash
.venv\Scripts\activate
```

#### macOS / Linux
```bash
source .venv/bin/activate
```

### 3. Install Dependencies

This project uses only the Python standard library, so there are no third-party packages to install.

If your Python installation does not include Tkinter:

#### Ubuntu / Debian
```bash
sudo apt-get update
sudo apt-get install python3-tk
```

#### Fedora
```bash
sudo dnf install python3-tkinter
```

#### Windows / macOS
Tkinter is typically included with the official Python installer.

---

## Running the Game

Start the application with:

```bash
python main.py
```

If your environment supports Tkinter, the graphical game window will open.

---

## Main Interface

When the game starts, you will see:

- A **title**
- The **current puzzle date**
- A **status message**
- A **mistake counter**
- A **selected words counter**
- Control buttons:
  - **Shuffle**
  - **Submit Guess**
  - **Clear Selection**
- A **4×4 word grid**
- A **feedback bar**
- A **solution history area** showing solved groups

---

## How to Play

### Step 1: Examine the Grid

You will see 16 words in a 4×4 layout.  
Your task is to find four sets of four words that belong together.

### Step 2: Select Four Words

Click words to select them.

- Selected words are visually highlighted
- You can select up to **4 words**
- Clicking a selected word again will deselect it

### Step 3: Submit Your Guess

After selecting 4 words, click:

**Submit Guess**

The game will immediately tell you whether the guess is:

- **Correct**
- **Incorrect**
- **Already solved**
- **Invalid** because fewer than 4 words are selected

### Step 4: Continue Solving

- Correct groups are removed from play
- The category name is revealed
- The solved group is displayed using its difficulty color
- Keep solving until all 4 groups are found or you reach 4 mistakes

---

## Buttons and Controls

### Shuffle

Rearranges the remaining unsolved words.

Use this when:

- You want a new visual layout
- You are unsure of the current arrangement
- You want to look for patterns more easily

### Submit Guess

Checks whether your current selection of 4 words forms a valid group.

### Clear Selection

Removes all currently selected words without submitting a guess.

---

## Feedback and Game Messages

The game gives immediate feedback in the message bar.

### Common Messages

- **"Word selected."**
- **"Word deselected."**
- **"4 selected — submit to check the group."**
- **"Select exactly four words."**
- **"Correct! [Category]"**
- **"Incorrect. Mistakes: X/4"**
- **"Incorrect. You have lost the puzzle."**
- **"That word can no longer be selected."**

---

## Difficulty Colors

Each solved group is labeled with a difficulty color:

- **Yellow** — easiest
- **Green**
- **Blue**
- **Purple** — hardest

These colors are displayed in the solved-groups panel after a correct guess.

---

## Mistakes and Game Over

You are allowed a maximum of **4 mistakes**.

### If you make a wrong guess:
- The mistake counter increases by 1

### If you reach 4 mistakes:
- The game ends
- The correct solution is shown in a popup
- All remaining words are disabled

### If you solve all groups:
- You win
- A congratulatory popup appears

---

## Daily Puzzle Behavior

The game uses the current date to choose a puzzle.

This means:

- A new puzzle is generated **daily**
- Everyone gets the same puzzle for the same day
- The word order is shuffled each time for presentation
- The underlying solution remains fixed

---

## Example Gameplay Flow

1. Open the game
2. Read the 16 words
3. Identify a possible category
4. Click 4 matching words
5. Click **Submit Guess**
6. If correct, the group is removed and revealed
7. Repeat until all 4 groups are solved

---

## Tips for Playing

- Look for obvious themes first
- Try to identify categories with the least ambiguity
- Remember that some words may seem to fit multiple groups
- Use **Shuffle** to view the board differently
- Keep track of mistakes carefully

---

## Troubleshooting

### The GUI does not open

Possible causes:

- Tkinter is not installed
- You are using a headless environment
- Your Python build does not include GUI support

### Fix

Install Tkinter for your operating system or run the game on a machine with a full Python GUI environment.

---

## Project Structure

- `main.py`  
  Application entry point

- `puzzle_data.py`  
  Stores the daily puzzle library and deterministic daily selection logic

- `game_logic.py`  
  Contains the core rules, guess validation, and game state management

- `ui.py`  
  Tkinter-based user interface

---

## Summary

**Daily Word Group Puzzle** is a polished word-association game where players must identify four hidden categories from a 4×4 grid of words.

### Key points:
- Group 16 words into 4 sets of 4
- Submit guesses one group at a time
- Receive immediate feedback
- Use shuffle to help solve
- Win by finding all groups before reaching 4 mistakes
- A new puzzle is available every day

Enjoy the puzzle!
```