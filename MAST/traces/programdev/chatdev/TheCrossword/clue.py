'''
Defines the Clue class and functions for loading and managing clues.
'''
class Clue:
    def __init__(self, number, text, position, direction, answer):
        self.number = number
        self.text = text
        self.position = position
        self.direction = direction
        self.answer = answer
def load_clues():
    # Example clues
    return [
        Clue(1, "A fruit", (0, 0), 'across', "apple"),
        Clue(2, "A color", (1, 0), 'down', "red"),
        # Add more clues as needed
    ]