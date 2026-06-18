```markdown
# Crossword Puzzle Application User Manual

A simple crossword puzzle game built in Python, with both a graphical interface and a console fallback.

---

## Overview

This application lets you solve a crossword puzzle by entering answers based on the clue number and direction:

- **Across** clues fill letters from left to right
- **Down** clues fill letters from top to bottom

The app validates your answers and checks for conflicting letters where words overlap. When all correct answers are filled in, the puzzle is marked complete.

---

## Main Features

- Crossword grid display with black squares and playable cells
- Clues grouped into **Across** and **Down**
- Answer submission by:
  - clue number
  - direction (`across` or `down`)
  - word answer
- Automatic validation of:
  - correct clue selection
  - correct spelling
  - matching overlapping letters
- Completion detection when all puzzle entries are correctly filled
- Two interfaces:
  - **Tkinter GUI** if available
  - **Console mode** fallback if Tkinter is unavailable

---

## Supported Environment

- Python 3.9+
- Tkinter (optional, for GUI mode)

If Tkinter is not available on your system, the application will automatically run in console mode.

---

## Installation

### 1. Install Python

Make sure Python is installed:

```bash
python --version
```

If Python is not installed, download it from:

- https://www.python.org/downloads/

---

### 2. Save the Project Files

Ensure the following files are in the same directory:

- `main.py`
- `puzzle.py`
- `crossword_gui.py`
- `crossword_cli.py`

---

### 3. Install Dependencies

This project uses only Python standard library modules.

#### GUI Mode
Tkinter is included with many Python distributions, but on some systems you may need to install it separately.

- **Ubuntu / Debian**
  ```bash
  sudo apt-get install python3-tk
  ```

- **Fedora**
  ```bash
  sudo dnf install python3-tkinter
  ```

- **Windows**
  Tkinter is usually included with the official Python installer.

- **macOS**
  Tkinter is commonly included, but some Python installations may require a version from python.org.

No additional `pip install` packages are required.

---

## How to Run

From the project folder, run:

```bash
python main.py
```

or:

```bash
python3 main.py
```

### What happens on launch?

- If Tkinter works, the graphical crossword window opens.
- If Tkinter is unavailable or cannot start, the app automatically switches to console mode.

---

## How to Play

### In the GUI Version

The window is split into two main sections:

1. **Left side**
   - Crossword grid
   - Black squares shown in black
   - Filled letters appear in the grid

2. **Right side**
   - Answer input form
   - Clue lists for Across and Down

#### Steps to submit an answer

1. Enter the **clue number**
2. Choose the **direction**:
   - `across`
   - `down`
3. Type the **answer**
4. Click **Submit**

If the answer is correct:

- The letters are placed into the grid
- Any overlapping letters must match
- The status bar updates with confirmation

If the answer is incorrect:

- A message box appears
- The grid is not updated

#### Puzzle completion

When every correct word has been entered, a completion message appears:

> Congratulations! You completed the crossword puzzle.

---

### In the Console Version

If Tkinter is unavailable, the application runs in the terminal.

#### Console workflow

1. The clues are displayed under **Across** and **Down**
2. The crossword grid is printed using:
   - `#` for black squares
   - `.` for empty playable cells
   - letters for filled cells

3. The app prompts you for:
   - clue number
   - direction
   - answer

4. Enter your response and press Enter

#### Example

```text
Clue number (or 'q' to quit): 1
Direction (across/down): across
Answer: CAT
```

If correct, the app prints:

```text
Correct!
```

If incorrect, it prints:

```text
Incorrect answer or conflicting letters.
```

---

## Crossword Validation Rules

The application checks answers carefully:

- The clue number and direction must exist
- The answer must exactly match the expected solution
- Letters shared by across and down words must agree
- Answers must fit inside the grid
- Black squares cannot be used

If a submitted answer causes a conflict, it will be rejected.

---

## Default Puzzle Included

The application includes a built-in sample crossword puzzle with simple clues such as:

- Small domesticated feline
- Male dog
- Written work with pages
- Natural satellite of Earth
- Night sky object that shines

This puzzle is small and designed to be fully solvable.

---

## Tips for Users

- Answers are **case-insensitive**: `cat`, `CAT`, and `Cat` are treated the same
- Enter the exact clue number shown in the clue list
- Make sure the direction is correct
- If a word is rejected, check whether it conflicts with already filled letters
- In console mode, you can quit by typing:
  - `q`
  - `quit`
  - `exit`

---

## Troubleshooting

### The GUI does not open
Possible reasons:
- Tkinter is not installed
- Your Python build does not include `_tkinter`
- The system cannot create a GUI window

**Solution:**
Run the app anyway. It will automatically fall back to console mode.

---

### I entered the right answer, but it was rejected
Possible reasons:
- Wrong clue number
- Wrong direction
- Typing mistake
- The word conflicts with an already placed crossing letter

---

### The console asks for input repeatedly
This usually means the answer was invalid or incomplete. Recheck the clue and try again.

---

## Project Structure

```text
main.py           # Application entry point
puzzle.py         # Crossword puzzle model, clues, and validation
crossword_gui.py  # Tkinter graphical interface
crossword_cli.py  # Console fallback interface
```

---

## Example Usage Summary

1. Start the app:
   ```bash
   python main.py
   ```
2. Read the clues
3. Enter clue number + direction + answer
4. Continue until all answers are filled
5. Receive completion confirmation

---

## License / Notes

This is a simple educational crossword application intended for demonstration and gameplay.

Enjoy solving the crossword puzzle!
```