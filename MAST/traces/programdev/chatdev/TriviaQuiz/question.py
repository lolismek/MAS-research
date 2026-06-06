'''
Defines the Question class for the trivia quiz program.
'''
class Question:
    def __init__(self, text, options, correct_answer_index):
        self.text = text
        self.options = options
        self.correct_answer_index = correct_answer_index
    def check_answer(self, selected_option_index):
        return selected_option_index == self.correct_answer_index