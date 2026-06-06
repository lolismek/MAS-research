'''
Defines the WordValidator class for validating word or phrase combinations.
'''
class WordValidator:
    def __init__(self, valid_words):
        self.valid_words = valid_words
    def is_valid(self, combination):
        return combination in self.valid_words