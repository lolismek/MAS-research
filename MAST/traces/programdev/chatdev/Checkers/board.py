'''
Board class to represent the checkers board and handle board-related logic.
'''
import pygame
from piece import Piece
from utils import position_to_coordinates
class Board:
    def __init__(self):
        self.grid = [[None for _ in range(8)] for _ in range(8)]
        self.setup_pieces()
    def setup_pieces(self):
        # Initialize pieces on the board
        for row in range(3):
            for col in range(8):
                if (row + col) % 2 == 1:
                    self.grid[row][col] = Piece('black', (row, col))
                    self.grid[7-row][7-col] = Piece('white', (7-row, 7-col))
    def draw(self, screen):
        screen.fill((255, 255, 255))
        for row in range(8):
            for col in range(8):
                color = (0, 0, 0) if (row + col) % 2 == 0 else (255, 255, 255)
                pygame.draw.rect(screen, color, (col * 100, row * 100, 100, 100))
                piece = self.grid[row][col]
                if piece:
                    piece.draw(screen)