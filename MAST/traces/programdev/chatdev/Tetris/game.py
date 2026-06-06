'''
Manages the main game loop and handles user input and game state updates.
'''
import pygame
from board import Board
from score import Score
from constants import SCREEN_WIDTH, SCREEN_HEIGHT
class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Tetris")
        self.clock = pygame.time.Clock()
        self.board = Board()
        self.score = Score()
        self.running = True
        self.drop_speed = 500  # Initial drop speed in milliseconds
        self.last_drop_time = pygame.time.get_ticks()
    def run(self):
        while self.running:
            self.handle_input()
            self.update()
            self.draw()
            self.clock.tick(60)
    def handle_input(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self.board.move_current_piece("left")
        if keys[pygame.K_RIGHT]:
            self.board.move_current_piece("right")
        if keys[pygame.K_DOWN]:
            self.board.move_current_piece("down")
        if keys[pygame.K_UP]:
            self.board.rotate_current_piece()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
    def update(self):
        current_time = pygame.time.get_ticks()
        # Increase drop speed as score increases
        self.drop_speed = max(100, 500 - (self.score.score // 500) * 50)  # Example: increase speed every 500 points
        if current_time - self.last_drop_time > self.drop_speed:
            if not self.board.move_current_piece("down"):
                self.board.add_piece(self.board.current_piece)
                lines_cleared = self.board.clear_lines()
                self.score.add_score(lines_cleared)
                self.board.spawn_new_piece()
                if not self.board.is_valid_position(self.board.current_piece):
                    self.running = False  # Game over
            self.last_drop_time = current_time
    def draw(self):
        self.screen.fill((0, 0, 0))
        self.board.draw(self.screen)
        self.score.draw(self.screen)
        pygame.display.flip()