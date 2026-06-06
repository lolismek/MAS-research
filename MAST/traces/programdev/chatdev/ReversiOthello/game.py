'''
Game logic for Reversi (Othello), managing game state and player actions.
'''
import pygame
from board import Board
class Game:
    def __init__(self, screen):
        self.screen = screen
        self.board = Board()
        self.current_player = 'B'
        self.valid_moves = self.get_valid_moves()
    def reset_game(self):
        self.board = Board()
        self.current_player = 'B'
        self.valid_moves = self.get_valid_moves()
    def get_valid_moves(self):
        valid_moves = []
        for row in range(8):
            for col in range(8):
                if self.board.grid[row][col] == ' ' and self.is_valid_move(row, col, self.current_player):
                    valid_moves.append((row, col))
        return valid_moves
    def is_valid_move(self, row, col, player):
        opponent = 'W' if player == 'B' else 'B'
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
        for dr, dc in directions:
            r, c = row + dr, col + dc
            if self.is_on_board(r, c) and self.board.grid[r][c] == opponent:
                while self.is_on_board(r, c) and self.board.grid[r][c] == opponent:
                    r += dr
                    c += dc
                if self.is_on_board(r, c) and self.board.grid[r][c] == player:
                    return True
        return False
    def is_on_board(self, row, col):
        return 0 <= row < 8 and 0 <= col < 8
    def make_move(self, row, col):
        self.board.update_board(row, col, self.current_player)
        self.flip_discs(row, col, self.current_player)
    def flip_discs(self, row, col, player):
        opponent = 'W' if player == 'B' else 'B'
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
        for dr, dc in directions:
            r, c = row + dr, col + dc
            discs_to_flip = []
            while self.is_on_board(r, c) and self.board.grid[r][c] == opponent:
                discs_to_flip.append((r, c))
                r += dr
                c += dc
            if self.is_on_board(r, c) and self.board.grid[r][c] == player:
                for rr, cc in discs_to_flip:
                    self.board.update_board(rr, cc, player)
    def check_winner(self):
        black_count = sum(row.count('B') for row in self.board.grid)
        white_count = sum(row.count('W') for row in self.board.grid)
        if black_count > white_count:
            return 'B'
        elif white_count > black_count:
            return 'W'
        else:
            return 'Draw'
    def switch_player(self):
        self.current_player = 'W' if self.current_player == 'B' else 'B'
        self.valid_moves = self.get_valid_moves()
    def handle_click(self, position):
        row, col = position[1] // 80, position[0] // 80
        if (row, col) in self.valid_moves:
            self.make_move(row, col)
            self.switch_player()
    def update(self):
        if not self.valid_moves:
            self.switch_player()
            if not self.valid_moves:
                winner = self.check_winner()
                print(f"Game Over! Winner: {winner}")
                pygame.quit()
                exit()
        else:
            self.display_score()
    def display_score(self):
        black_count = sum(row.count('B') for row in self.board.grid)
        white_count = sum(row.count('W') for row in self.board.grid)
        print(f"Score - Black: {black_count}, White: {white_count}")
    def draw(self):
        self.board.draw_board(self.screen)