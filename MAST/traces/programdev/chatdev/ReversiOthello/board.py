'''
Board rendering and state management for Reversi (Othello).
'''
import pygame
class Board:
    def __init__(self):
        self.grid = [[' ' for _ in range(8)] for _ in range(8)]
        self.grid[3][3] = 'W'
        self.grid[3][4] = 'B'
        self.grid[4][3] = 'B'
        self.grid[4][4] = 'W'
    def draw_board(self, screen):
        screen.fill((0, 128, 0))
        for row in range(8):
            for col in range(8):
                pygame.draw.rect(screen, (0, 0, 0), (col * 80, row * 80, 80, 80), 1)
                if self.grid[row][col] == 'B':
                    pygame.draw.circle(screen, (0, 0, 0), (col * 80 + 40, row * 80 + 40), 30)
                elif self.grid[row][col] == 'W':
                    pygame.draw.circle(screen, (255, 255, 255), (col * 80 + 40, row * 80 + 40), 30)
    def update_board(self, row, col, player):
        self.grid[row][col] = player