# Trivia Quiz Program

Welcome to the Trivia Quiz Program! This application is designed to provide an engaging and educational experience through a series of trivia questions on various topics. The program allows users to answer multiple-choice questions, track their scores, and review correct answers at the end of the quiz.

## Main Functions

- **Multiple-Choice Questions**: The program presents questions with multiple-choice answers. Users select the answer they believe is correct.
- **Score Tracking**: The program keeps track of the user's score throughout the quiz.
- **Configurable Question Bank**: Users can customize the question bank by modifying the `questions.json` file.
- **Review Correct Answers**: After completing the quiz, users can view the correct answers for all questions.

## Installation

### Environment Setup

This program is written in Python and uses the Tkinter library for the graphical user interface. Ensure you have Python 3.x installed on your system, as Tkinter is included with Python.

1. **Install Python 3.x**: Download and install Python from the [official website](https://www.python.org/downloads/).

2. **Verify Tkinter Installation**: Tkinter is included with Python, but you can verify its installation by running the following command in your terminal or command prompt:
   ```bash
   python -m tkinter
   ```
   If a small window appears, Tkinter is installed correctly.

3. **No Additional Dependencies**: This project does not require any external dependencies beyond Python and Tkinter.

## How to Use

1. **Download the Program Files**: Ensure you have the following files in the same directory:
   - `main.py`
   - `question.py`
   - `question_bank.py`
   - `questions.json`

2. **Run the Program**: Open a terminal or command prompt, navigate to the directory containing the program files, and execute the following command:
   ```bash
   python main.py
   ```

3. **Play the Quiz**:
   - The program will open a window displaying the first trivia question.
   - Select your answer by clicking on one of the multiple-choice options.
   - The program will automatically proceed to the next question after you select an answer.
   - Continue answering questions until the quiz is complete.

4. **View Results**:
   - After answering all questions, a message box will display your score and the correct answers for each question.
   - Review your performance and learn from the correct answers.

5. **Customize Questions**:
   - To add or modify questions, edit the `questions.json` file.
   - Ensure each question follows the format:
     ```json
     {
         "text": "Question text",
         "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
         "correct_answer_index": 0
     }
     ```
   - Save the file and restart the program to see the changes.

Enjoy your trivia experience and enhance your knowledge with the Trivia Quiz Program!