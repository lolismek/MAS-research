'''
GomokuGame class manages the game logic for the Gomoku game.
'''
class GomokuGame:
    def __init__(self):
        self.board_size = 15
        self.board = [[None for _ in range(self.board_size)] for _ in range(self.board_size)]
        self.current_player = "black"
    def place_stone(self, x, y):
        if self.board[y][x] is not None:
            return "Position already occupied. Try another move."
        self.board[y][x] = self.current_player
        if self.check_win(x, y):
            return f"{self.current_player} wins!"
        self.current_player = "white" if self.current_player == "black" else "black"
        return None
    def check_win(self, x, y):
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dx, dy in directions:
            count = 1
            for step in range(1, 5):
                nx, ny = x + step * dx, y + step * dy
                if 0 <= nx < self.board_size and 0 <= ny < self.board_size and self.board[ny][nx] == self.current_player:
                    count += 1
                else:
                    break
            for step in range(1, 5):
                nx, ny = x - step * dx, y - step * dy
                if 0 <= nx < self.board_size and 0 <= ny < self.board_size and self.board[ny][nx] == self.current_player:
                    count += 1
                else:
                    break
            if count >= 5:
                return True
        return False
    def reset_game(self):
        self.board = [[None for _ in range(self.board_size)] for _ in range(self.board_size)]
        self.current_player = "black"