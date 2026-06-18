```markdown
# Wordle Terminal Edition

A terminal-based Wordle game for Linux that lets you guess a daily 5-letter English word in 6 attempts with proper color feedback.

## Overview

This project implements a standard Wordle-like experience in the Linux terminal:

- A **daily answer word** is selected deterministically from a curated 5-letter English word list.
- The player has **6 attempts** to guess the word.
- Each guess is evaluated and printed directly in the terminal:
  - **Green**: correct letter in the correct position
  - **Yellow**: correct letter in the wrong position
  - **Grey**: letter not in the word
- Guess input is validated before scoring.
- If the player solves the word within 6 attempts, they win.
- If not, the correct answer is revealed at the end.

---

## Main Features

- **Daily word selection**
  - The game uses the current date to consistently choose one answer word for that day.
  - The same date always maps to the same word.

- **6-turn gameplay**
  - The player is allowed up to 6 valid guesses.

- **Word validation**
  - Guesses must:
    - be exactly 5 letters long
    - contain only alphabetic characters
    - exist in the accepted guess list

- **Wordle scoring rules**
  - Proper handling of repeated letters using standard Wordle-style scoring logic.

- **Terminal-friendly output**
  - Uses ANSI colors when supported by the terminal.
  - Falls back to plain-text markers if color output is unavailable.

- **Graceful exit**
  - Handles input interruption or unavailable input safely.

---

## Project Files

### `main.py`
Entry point of the application.  
It creates a `WordleGame` instance and starts the game.

### `wordle_game.py`
Contains the game logic:
- daily answer selection
- guess validation
- scoring
- colored output formatting
- interactive play loop

### `word_list.py`
Contains:
- `ANSWER_LIST`: words eligible to be the daily solution
- `VALID_GUESS_LIST`: accepted guess words

---

## Requirements

- Python **3.9+** recommended
- Linux terminal
- A terminal that supports ANSI color codes is recommended, but not required

No third-party Python packages are needed.

---

## Installation

### 1. Verify Python is installed

Check your Python version:

```bash
python3 --version
```

If Python is not installed, install it using your Linux distribution’s package manager.

#### Ubuntu / Debian
```bash
sudo apt update
sudo apt install python3
```

#### Fedora
```bash
sudo dnf install python3
```

#### Arch Linux
```bash
sudo pacman -S python
```

---

### 2. Save the files

Make sure the project directory contains these files:

```text
main.py
wordle_game.py
word_list.py
manual.md
```

---

### 3. Run the game

From the project directory, execute:

```bash
python3 main.py
```

If your system uses `python` for Python 3, this also works:

```bash
python main.py
```

---

## How to Play

After launching the game, you will see instructions in the terminal.

Example start screen:

```text
========================================
WORDLE - Terminal Edition
========================================
Date: 2026-06-18
Guess the 5-letter word in 6 attempts.
Feedback: Green = correct position, Yellow = wrong position, Grey = not in word.
```

You will then be prompted to enter a guess:

```text
Attempt 1/6 (6 left):
```

Type a 5-letter English word and press Enter.

---

## Feedback Rules

After each valid guess, the game prints feedback for each letter:

- **Green**: the letter is correct and in the correct position
- **Yellow**: the letter is in the answer, but in a different position
- **Grey**: the letter is not present in the answer

### ANSI Color Output

If your terminal supports ANSI colors, the result will appear colored directly in the terminal.

### Plain Text Fallback

If ANSI colors are unavailable, the game uses markers:

- `[G]` = green
- `[Y]` = yellow
- `[.]` = grey

Example:

```text
[G]C [Y]R [.]A [.]N [G]E
```

---

## Guess Validation

Before scoring, every guess is validated.

Your guess must:

1. Be exactly **5 characters**
2. Contain only letters
3. Be included in the accepted guess list

### Invalid Guess Examples

- `cat` → too short
- `abc12` → contains non-letters
- `qwert` → not in the accepted list

If your guess is invalid, the game will print an error message and let you try again without consuming an attempt.

---

## Winning and Losing

### Win Condition
If you guess the word correctly within 6 valid attempts, the game ends with a success message:

```text
🎉 Congratulations! You guessed the word!
```

### Lose Condition
If you do not guess the word in 6 attempts, the correct answer is shown:

```text
Game over. The correct word was: CRANE
```

---

## Daily Word Behavior

The solution word is selected based on the current calendar date.

This means:

- the same day always uses the same answer
- the answer changes on the next day
- the selection is deterministic across environments

This is useful for consistent daily play.

---

## Example Session

```text
========================================
WORDLE - Terminal Edition
========================================
Date: 2026-06-18
Guess the 5-letter word in 6 attempts.
Feedback: Green = correct position, Yellow = wrong position, Grey = not in word.

Attempt 1/6 (6 left): crane
[G]C [G]R [G]A [G]N [G]E

🎉 Congratulations! You guessed the word!
```

Another example:

```text
Attempt 1/6 (6 left): apple
[.]A [.]P [Y]P [.]L [.]E

Attempt 2/6 (5 left): place
[Y]P [.]L [.]A [.]C [.]E
```

---

## How the Scoring Works

The scoring algorithm follows Wordle-style rules and handles repeated letters correctly.

### Two-pass scoring approach

1. **First pass**
   - Marks all letters that are in the correct position as green.
   - Reduces available letter counts in the answer.

2. **Second pass**
   - Marks remaining letters yellow if they still exist in the answer and have not already been fully matched.
   - Otherwise marks them grey.

This ensures proper feedback even when guesses or answers contain repeated letters.

---

## Terminal Compatibility

The game tries to detect whether ANSI colors are supported.

### Colors are enabled when:
- output is attached to a terminal
- `TERM` is not `dumb`

### Colors are disabled when:
- output is redirected to a file
- the terminal environment does not support ANSI color codes

In those cases, the game still works and uses plain-text markers.

---

## Troubleshooting

### 1. `python3: command not found`
Python is not installed or not available in your PATH. Install Python 3 using your distribution’s package manager.

### 2. Colors do not appear
Your terminal may not support ANSI colors, or output may be redirected. The game will still work using text markers.

### 3. “Word not in accepted word list.”
The guess is not in the accepted list defined in `word_list.py`. Try a different valid 5-letter English word.

### 4. Input exits immediately
This can happen if:
- standard input is unavailable
- you are running in a non-interactive environment

Run the game in a normal Linux terminal session.

---

## Customization

If you want to change the game behavior, you can edit the following files:

### `word_list.py`
- Add or remove valid answer words
- Add more accepted guesses

### `wordle_game.py`
- Change `MAX_ATTEMPTS`
- Change `WORD_LENGTH`
- Modify color formatting
- Adjust daily word selection logic

---

## Notes for Developers

- The game currently uses a curated word list rather than a full dictionary.
- All answer words are validated at startup.
- The implementation is self-contained and has no external dependency requirements.

---

## License

If you plan to distribute this project, add your preferred license here.

---

## Support

For issues or feature requests, consider extending:
- word list size
- replay mode
- statistics tracking
- hard mode rules
- custom word input mode
```

