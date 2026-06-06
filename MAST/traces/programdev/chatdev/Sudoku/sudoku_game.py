'''
Defines the SudokuGame class for managing the game state.
'''
from sudoku_grid import SudokuGrid
class SudokuGame:
    def __init__(self):
        '''
        Initialize the Sudoku game with a SudokuGrid.
        '''
        self.grid = SudokuGrid()
    def input_value(self, row, col, value):
        '''
        Input a value into the grid and check if it's valid.
        '''
        if self.grid.is_valid(row, col, value):
            self.grid.set_value(row, col, value)
            return True
        return False
    def check_completion(self):
        '''
        Check if the Sudoku puzzle is completed.
        '''
        return self.grid.is_complete()