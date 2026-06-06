'''
Manages the game loop and user interactions for the match-3 puzzle game.
'''
import pygame
from game_board import GameBoard
from score_manager import ScoreManager
class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((600, 600))
        pygame.display.set_caption("Match-3 Puzzle Game")
        self.clock = pygame.time.Clock()
        self.board = GameBoard(8, 8)
        self.score_manager = ScoreManager()
        self.running = True
        self.first_selected = None
    def run(self):
        while self.running:
            self.handle_events()
            self.board.update_board(self.score_manager)
            self.draw()
            self.clock.tick(60)
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.first_selected = self.get_candy_at_mouse_position(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP:
                second_selected = self.get_candy_at_mouse_position(event.pos)
                if self.first_selected and second_selected:
                    if self.are_adjacent(self.first_selected, second_selected):
                        self.board.swap_candies(self.first_selected, second_selected)
                        self.board.update_board(self.score_manager)
                    self.first_selected = None
    def get_candy_at_mouse_position(self, pos):
        x, y = pos
        row = y // 75
        col = x // 75
        if 0 <= row < self.board.rows and 0 <= col < self.board.cols:
            return (row, col)
        return None
    def are_adjacent(self, pos1, pos2):
        r1, c1 = pos1
        r2, c2 = pos2
        return abs(r1 - r2) + abs(c1 - c2) == 1
    def draw(self):
        self.screen.fill((255, 255, 255))
        self.board.draw(self.screen)
        font = pygame.font.Font(None, 36)
        score_text = font.render(f"Score: {self.score_manager.score}", True, (0, 0, 0))
        self.screen.blit(score_text, (10, 10))
        pygame.display.flip()