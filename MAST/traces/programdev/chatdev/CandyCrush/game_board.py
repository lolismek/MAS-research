'''
Represents the game board and handles the logic for swapping candies, checking for matches, clearing matches, and updating the board.
'''
import random
import pygame
from candy import Candy
class GameBoard:
    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.board = [[Candy(random.choice(['red', 'green', 'blue', 'yellow']), (r, c)) for c in range(cols)] for r in range(rows)]
    def swap_candies(self, pos1, pos2):
        r1, c1 = pos1
        r2, c2 = pos2
        self.board[r1][c1], self.board[r2][c2] = self.board[r2][c2], self.board[r1][c1]
    def find_matches(self):
        matches = []
        for r in range(self.rows):
            for c in range(self.cols - 2):
                if self.board[r][c].color == self.board[r][c+1].color == self.board[r][c+2].color:
                    matches.append((r, c))
                    matches.append((r, c+1))
                    matches.append((r, c+2))
        for c in range(self.cols):
            for r in range(self.rows - 2):
                if self.board[r][c].color == self.board[r+1][c].color == self.board[r+2][c].color:
                    matches.append((r, c))
                    matches.append((r+1, c))
                    matches.append((r+2, c))
        return list(set(matches))
    def clear_matches(self, matches, score_manager):
        for r, c in matches:
            self.board[r][c] = None
        score_manager.add_score(len(matches))
    def drop_candies(self):
        for c in range(self.cols):
            empty_spots = 0
            for r in range(self.rows - 1, -1, -1):
                if self.board[r][c] is None:
                    empty_spots += 1
                elif empty_spots > 0:
                    self.board[r + empty_spots][c] = self.board[r][c]
                    self.board[r][c] = None
    def refill_board(self):
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] is None:
                    self.board[r][c] = Candy(random.choice(['red', 'green', 'blue', 'yellow']), (r, c))
    def update_board(self, score_manager):
        while True:
            matches = self.find_matches()
            if not matches:
                break
            self.clear_matches(matches, score_manager)
            self.drop_candies()
            self.refill_board()
    def draw(self, screen):
        for r in range(self.rows):
            for c in range(self.cols):
                candy = self.board[r][c]
                if candy:
                    pygame.draw.circle(screen, self.get_color(candy.color), (c * 75 + 37, r * 75 + 37), 30)
    def get_color(self, color_name):
        colors = {
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'yellow': (255, 255, 0)
        }
        return colors[color_name]