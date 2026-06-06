'''
Represents the Tetris board and handles Tetromino placement and line clearing.
'''
import pygame
from tetromino import Tetromino
from constants import BOARD_WIDTH, BOARD_HEIGHT, BLOCK_SIZE
class Board:
    def __init__(self):
        self.grid = [[0] * BOARD_WIDTH for _ in range(BOARD_HEIGHT)]
        self.current_piece = Tetromino()
        self.next_piece = Tetromino()
    def clear_lines(self):
        lines_to_clear = [i for i, row in enumerate(self.grid) if all(row)]
        for i in lines_to_clear:
            del self.grid[i]
            self.grid.insert(0, [0] * BOARD_WIDTH)
        return len(lines_to_clear)
    def is_valid_position(self, piece, offset=(0, 0)):
        for y, row in enumerate(piece.shape):
            for x, cell in enumerate(row):
                if cell:
                    new_x = x + piece.position[0] + offset[0]
                    new_y = y + piece.position[1] + offset[1]
                    if new_x < 0 or new_x >= BOARD_WIDTH or new_y >= BOARD_HEIGHT:
                        return False
                    if new_y >= 0 and self.grid[new_y][new_x]:
                        return False
        return True
    def add_piece(self, piece):
        for y, row in enumerate(piece.shape):
            for x, cell in enumerate(row):
                if cell:
                    self.grid[y + piece.position[1]][x + piece.position[0]] = cell
    def remove_piece(self, piece):
        for y, row in enumerate(piece.shape):
            for x, cell in enumerate(row):
                if cell:
                    self.grid[y + piece.position[1]][x + piece.position[0]] = 0
    def move_current_piece(self, direction):
        self.remove_piece(self.current_piece)
        self.current_piece.move(direction)
        if not self.is_valid_position(self.current_piece):
            self.current_piece.move("left" if direction == "right" else "right" if direction == "left" else "up")
            self.add_piece(self.current_piece)  # Ensure the piece is added back
            return False
        self.add_piece(self.current_piece)
        return True
    def rotate_current_piece(self):
        self.remove_piece(self.current_piece)
        self.current_piece.rotate()
        # Check if the piece is out of bounds and adjust its position
        if not self.is_valid_position(self.current_piece):
            # Try moving the piece left or right to fit it within bounds
            for offset in range(-2, 3):
                if self.is_valid_position(self.current_piece, (offset, 0)):
                    self.current_piece.position[0] += offset
                    break
            else:
                # If no valid position is found, rotate back to the original orientation
                self.current_piece.rotate()
                self.current_piece.rotate()
                self.current_piece.rotate()
        self.add_piece(self.current_piece)
    def spawn_new_piece(self):
        self.current_piece = self.next_piece
        self.next_piece = Tetromino()
    def draw(self, screen):
        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                if cell:
                    pygame.draw.rect(screen, (255, 255, 255), 
                                     (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))
        self.current_piece.draw(screen)