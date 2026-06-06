'''
Handles the crossword grid, including word placement and validation.
'''
class CrosswordGrid:
    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.grid = [['' for _ in range(cols)] for _ in range(rows)]
    def place_word(self, clue, word):
        row, col = clue.position
        if clue.direction == 'across':
            for i, letter in enumerate(word):
                self.grid[row][col + i] = letter
        elif clue.direction == 'down':
            for i, letter in enumerate(word):
                self.grid[row + i][col] = letter
    def validate_word(self, clue, word):
        row, col = clue.position
        if clue.direction == 'across':
            return all(self.grid[row][col + i] in ('', letter) for i, letter in enumerate(word))
        elif clue.direction == 'down':
            return all(self.grid[row + i][col] in ('', letter) for i, letter in enumerate(word))
    def is_complete(self):
        return all(all(cell != '' for cell in row) for row in self.grid)