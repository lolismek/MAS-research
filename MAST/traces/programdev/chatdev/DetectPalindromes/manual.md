# Palindrome Detector

A simple application to detect palindromes in a given text file using a graphical user interface (GUI) built with Tkinter.

## Introduction

The Palindrome Detector is a Python application designed to identify palindromes within a text file. A palindrome is a word that reads the same backward as forward, such as "radar" or "level". This application provides a user-friendly interface to load a text file and display any palindromes found within the file.

## Quick Install

### Prerequisites

Ensure you have Python installed on your system. You can download it from [python.org](https://www.python.org/downloads/).

### Installation

1. Clone the repository or download the source code to your local machine.

2. Navigate to the directory containing the source code.

3. Since there are no external dependencies required for this project, you can directly run the application without additional installations.

## How to Use

1. **Run the Application:**

   Open a terminal or command prompt, navigate to the directory containing the `main.py` file, and execute the following command:

   ```bash
   python main.py
   ```

2. **Load a Text File:**

   - Upon launching the application, you will see a window titled "Palindrome Detector".
   - Click on the "Load File" button to open a file dialog.
   - Select a text file (`*.txt`) from your system that you wish to analyze for palindromes.

3. **View Results:**

   - Once a file is loaded, the application will process the text and display any palindromes found in the text area below the "Load File" button.
   - If no palindromes are found, the message "No palindromes found." will be displayed.

## Main Functions

- **Load File:** Allows users to select a text file from their system.
- **Detect Palindromes:** Processes the text to identify and list palindromes.
- **Display Results:** Shows the results in the application window.

## Documentation

For further details on the implementation, refer to the source code files:

- `main.py`: Contains the main application logic and GUI setup.
- `utils.py`: Includes utility functions such as `is_palindrome` to check if a word is a palindrome.

## Support

For any issues or questions, please contact our support team or visit our [GitHub repository](https://github.com/your-repo-link) for more information.

---

Enjoy using the Palindrome Detector to explore the fascinating world of palindromes in your text files!