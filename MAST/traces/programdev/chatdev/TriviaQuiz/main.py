'''
Main application file for the trivia quiz program using tkinter.
'''
import tkinter as tk
from tkinter import messagebox
from question import Question
from question_bank import QuestionBank
class QuizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Trivia Quiz")
        self.score = 0
        self.current_question_index = 0
        self.questions = self.load_questions()
        self.question_label = tk.Label(root, text="", wraplength=400, justify="left")
        self.question_label.pack(pady=20)
        self.option_buttons = []
        for i in range(4):
            btn = tk.Button(root, text="", command=lambda i=i: self.check_answer(i))
            btn.pack(fill="x", padx=20, pady=5)
            self.option_buttons.append(btn)
        self.start_quiz()
    def load_questions(self):
        # Load questions from a configurable question bank
        question_bank = QuestionBank("questions.json")
        return question_bank.questions
    def start_quiz(self):
        self.score = 0
        self.current_question_index = 0
        self.display_question()
    def display_question(self):
        question = self.questions[self.current_question_index]
        self.question_label.config(text=question.text)
        for i, option in enumerate(question.options):
            self.option_buttons[i].config(text=option)
    def check_answer(self, selected_option_index):
        question = self.questions[self.current_question_index]
        if question.check_answer(selected_option_index):
            self.score += 1
        self.current_question_index += 1
        if self.current_question_index < len(self.questions):
            self.display_question()
        else:
            self.show_results()
    def show_results(self):
        result_text = f"You scored {self.score} out of {len(self.questions)}\n\n"
        result_text += "Correct Answers:\n"
        for i, question in enumerate(self.questions):
            correct_option = question.options[question.correct_answer_index]
            result_text += f"Q{i+1}: {question.text}\nCorrect Answer: {correct_option}\n\n"
        messagebox.showinfo("Quiz Results", result_text)
        self.root.quit()
if __name__ == "__main__":
    root = tk.Tk()
    app = QuizApp(root)
    root.mainloop()