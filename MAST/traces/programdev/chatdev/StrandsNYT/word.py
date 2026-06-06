'''
Represents individual words on the board, including their position, direction, and type.
'''
class Word:
    def __init__(self, text, start_pos, direction, word_type):
        self.text = text
        self.start_pos = start_pos
        self.direction = direction
        self.word_type = word_type
    def get_positions(self):
        # Calculate and return all positions occupied by this word
        positions = []
        x, y = self.start_pos
        for i in range(len(self.text)):
            positions.append((x, y))
            if self.direction == 'horizontal':
                y += 1
            elif self.direction == 'vertical':
                x += 1
            elif self.direction == 'diagonal':
                x += 1
                y += 1
        return positions