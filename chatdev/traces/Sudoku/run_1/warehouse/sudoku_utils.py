'''
Utility functions for Sudoku:
- validation
- solving
- generation
- completion checking
- uniqueness checking
'''
import copy
import random
def is_valid_move(board, row, col, num):
    '''Return True if placing num at board[row][col] is valid.'''
    if not (1 <= num <= 9):
        return False
    for c in range(9):
        if c != col and board[row][c] == num:
            return False
    for r in range(9):
        if r != row and board[r][col] == num:
            return False
    start_row = (row // 3) * 3
    start_col = (col // 3) * 3
    for r in range(start_row, start_row + 3):
        for c in range(start_col, start_col + 3):
            if (r != row or c != col) and board[r][c] == num:
                return False
    return True
def is_board_valid(board):
    '''Check whether a completed board contains digits 1 through 9 exactly once in every row, column, and 3x3 box.'''
    expected = set(range(1, 10))
    for r in range(9):
        if set(board[r]) != expected:
            return False
    for c in range(9):
        col_vals = {board[r][c] for r in range(9)}
        if col_vals != expected:
            return False
    for br in range(0, 9, 3):
        for bc in range(0, 9, 3):
            box = set()
            for r in range(br, br + 3):
                for c in range(bc, bc + 3):
                    box.add(board[r][c])
            if box != expected:
                return False
    return True
def find_empty(board):
    '''Find the next empty cell (value 0). Return (row, col) or None.'''
    for r in range(9):
        for c in range(9):
            if board[r][c] == 0:
                return r, c
    return None
def solve_board(board):
    '''Solve the Sudoku board in-place using backtracking.'''
    empty = find_empty(board)
    if empty is None:
        return is_board_valid(board)
    row, col = empty
    nums = list(range(1, 10))
    random.shuffle(nums)
    for num in nums:
        if is_valid_move(board, row, col, num):
            board[row][col] = num
            if solve_board(board):
                return True
            board[row][col] = 0
    return False
def count_solutions(board, limit=2):
    '''Count the number of solutions for a board up to a given limit.'''
    empty = find_empty(board)
    if empty is None:
        return 1 if is_board_valid(board) else 0
    row, col = empty
    total = 0
    for num in range(1, 10):
        if is_valid_move(board, row, col, num):
            board[row][col] = num
            total += count_solutions(board, limit)
            board[row][col] = 0
            if total >= limit:
                return total
    return total
def has_unique_solution(board):
    '''Return True if the board has exactly one solution.'''
    temp = copy.deepcopy(board)
    return count_solutions(temp, limit=2) == 1
def generate_full_board():
    '''Generate a complete valid Sudoku solution.'''
    board = [[0 for _ in range(9)] for _ in range(9)]
    solved = solve_board(board)
    if not solved or not is_board_valid(board):
        raise RuntimeError("Failed to generate a valid completed Sudoku board.")
    return board
def generate_puzzle(empty_cells=45):
    '''
    Generate a Sudoku puzzle and its solution.
    Cells are removed one by one while preserving a unique solution.
    If the requested number of empty cells cannot be reached reliably,
    generation retries until a valid unique puzzle is produced.
    '''
    empty_cells = max(0, min(81, int(empty_cells)))
    for _ in range(100):
        solution = generate_full_board()
        puzzle = copy.deepcopy(solution)
        cells = [(r, c) for r in range(9) for c in range(9)]
        random.shuffle(cells)
        removed = 0
        for r, c in cells:
            if removed >= empty_cells:
                break
            backup = puzzle[r][c]
            puzzle[r][c] = 0
            if has_unique_solution(puzzle):
                removed += 1
            else:
                puzzle[r][c] = backup
        if removed == empty_cells and has_unique_solution(puzzle):
            return puzzle, solution
    raise RuntimeError("Failed to generate a Sudoku puzzle with a unique solution.")
def board_is_complete(board):
    '''Check whether a board has no empty cells and is valid, without mutating input.'''
    for r in range(9):
        for c in range(9):
            if board[r][c] == 0:
                return False
            if not (1 <= board[r][c] <= 9):
                return False
    return is_board_valid(board)