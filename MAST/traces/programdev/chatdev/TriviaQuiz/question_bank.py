'''
Defines the QuestionBank class to manage a collection of questions.
'''
import json
from question import Question
class QuestionBank:
    def __init__(self, file_path="questions.json"):
        self.questions = self.load_questions_from_file(file_path)
    def load_questions_from_file(self, file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
            return [Question(q['text'], q['options'], q['correct_answer_index']) for q in data]