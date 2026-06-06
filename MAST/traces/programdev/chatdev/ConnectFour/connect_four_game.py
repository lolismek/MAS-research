'''
Contains the game logic for Connect Four.
'''
class ConnectFourGame:
    ROWS = 6
    COLUMNS = 7
    def __init__(self):
        self.board = [['' for _ in range(self.COLUMNS)] for _ in range(self.ROWS)]
        self.current_player = 'Red'
    def drop_disc(self, column):
        for row in reversed(range(self.ROWS)):
            if self.board[row][column] == '':
                self.board[row][column] = self.current_player
                return row, column
        return None
    def check_winner(self, row, column):
        return (self.check_line(row, column, 1, 0) or  # Horizontal
                self.check_line(row, column, 0, 1) or  # Vertical
                self.check_line(row, column, 1, 1) or  # Diagonal /
                self.check_line(row, column, 1, -1))   # Diagonal \
    def check_line(self, row, column, delta_row, delta_col):
        count = 0
        for d in range(-3, 4):
            r = row + d * delta_row
            c = column + d * delta_col
            if 0 <= r < self.ROWS and 0 <= c < self.COLUMNS and self.board[r][c] == self.current_player:
                count += 1
                if count == 4:
                    return True
            else:
                count = 0
        return False
    def is_draw(self):
        return all(self.board[0][col] != '' for col in range(self.COLUMNS))
    def switch_player(self):
        self.current_player = 'Yellow' if self.current_player == 'Red' else 'Red'