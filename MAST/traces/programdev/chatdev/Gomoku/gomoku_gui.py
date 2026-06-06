'''
GomokuGUI class handles the graphical user interface using Pygame.
'''
import pygame
from gomoku_game import GomokuGame
class GomokuGUI:
    def __init__(self):
        pygame.init()
        self.screen_size = 600
        self.cell_size = self.screen_size // 15
        self.screen = pygame.display.set_mode((self.screen_size, self.screen_size))
        pygame.display.set_caption("Gomoku")
        self.game = GomokuGame()
        self.running = True
    def draw_board(self):
        self.screen.fill((255, 255, 255))
        for x in range(15):
            for y in range(15):
                rect = pygame.Rect(x * self.cell_size, y * self.cell_size, self.cell_size, self.cell_size)
                pygame.draw.rect(self.screen, (0, 0, 0), rect, 1)
                if self.game.board[y][x] == "black":
                    pygame.draw.circle(self.screen, (0, 0, 0), rect.center, self.cell_size // 2 - 2)
                elif self.game.board[y][x] == "white":
                    pygame.draw.circle(self.screen, (255, 255, 255), rect.center, self.cell_size // 2 - 2)
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                x, y = event.pos
                grid_x, grid_y = x // self.cell_size, y // self.cell_size
                result = self.game.place_stone(grid_x, grid_y)
                if result:
                    print(result)
                    if "wins" in result:
                        self.game.reset_game()
    def run(self):
        while self.running:
            self.handle_events()
            self.draw_board()
            pygame.display.flip()
        pygame.quit()