'''
Main entry point for the Sudoku game application.
'''
from sudoku_gui import SudokuGUI
def main():
    '''
    Initialize and run the Sudoku game.
    '''
    game = SudokuGUI()
    game.run()
if __name__ == "__main__":
    main()