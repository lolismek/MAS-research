'''
Defines the SudokuGrid class for managing the Sudoku grid logic.
'''
class SudokuGrid:
    def __init__(self):
        '''
        Initialize a 9x9 Sudoku grid with zeros (empty cells).
        '''
        self.grid = [[0 for _ in range(9)] for _ in range(9)]
    def set_value(self, row, col, value):
        '''
        Set a value in the grid at the specified row and column.
        '''
        if 1 <= value <= 9:
            self.grid[row][col] = value
    def is_valid(self, row, col, value):
        '''
        Check if placing a value at the specified row and column is valid.
        '''
        # Check row and column
        for i in range(9):
            if self.grid[row][i] == value or self.grid[i][col] == value:
                return False
        # Check 3x3 subgrid
        start_row, start_col = 3 * (row // 3), 3 * (col // 3)
        for i in range(start_row, start_row + 3):
            for j in range(start_col, start_col + 3):
                if self.grid[i][j] == value:
                    return False
        return True
    def is_complete(self):
        '''
        Check if the Sudoku puzzle is completed correctly.
        '''
        # Check rows and columns
        for i in range(9):
            if sorted(self.grid[i]) != list(range(1, 10)):
                return False
            if sorted([self.grid[j][i] for j in range(9)]) != list(range(1, 10)):
                return False
        # Check 3x3 subgrids
        for start_row in range(0, 9, 3):
            for start_col in range(0, 9, 3):
                subgrid = []
                for i in range(3):
                    for j in range(3):
                        subgrid.append(self.grid[start_row + i][start_col + j])
                if sorted(subgrid) != list(range(1, 10)):
                    return False
        return True