'''
Puzzle logic for managing word grouping, shuffling, and checking guesses.
'''
import random
class Puzzle:
    def __init__(self, words, categories, difficulty_colors):
        '''
        Initializes the Puzzle with words, categories, and difficulty colors.
        '''
        self.words = words
        self.categories = categories
        self.difficulty_colors = difficulty_colors
        self.selected_words = []
        self.correct_groups = []
    def shuffle_words(self):
        '''
        Shuffles the words in the puzzle.
        '''
        random.shuffle(self.words)
    def check_group(self, selected_words):
        '''
        Checks if the selected words form a correct group.
        Returns the category and its color if correct, otherwise None.
        '''
        for category, words in self.categories.items():
            if set(selected_words) == set(words):
                return category, self.difficulty_colors[category]
        return None, None
    def remove_correct_group(self, group):
        '''
        Removes the correct group from the grid and adds it to correct groups.
        '''
        self.correct_groups.append(group)
        for word in group:
            self.words.remove(word)