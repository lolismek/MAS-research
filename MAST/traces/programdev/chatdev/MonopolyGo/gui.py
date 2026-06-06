'''
Handles all graphical elements and user interactions.
'''
import pygame
from property import Property
class GUI:
    def __init__(self, board, players):
        pygame.init()
        self.screen = pygame.display.set_mode((800, 600))
        self.board = board
        self.players = players
        self.font = pygame.font.SysFont(None, 36)
    def draw_board(self):
        self.screen.fill((255, 255, 255))
        # Draw properties and player positions
        for i, space in enumerate(self.board.spaces):
            x = (i % 10) * 80
            y = (i // 10) * 80
            pygame.draw.rect(self.screen, (0, 0, 0), (x, y, 80, 80), 1)
            if isinstance(space, Property):
                text = self.font.render(space.name, True, (0, 0, 0))
                self.screen.blit(text, (x + 5, y + 5))
            for player in self.players:
                if player.position == i:
                    pygame.draw.circle(self.screen, (255, 0, 0), (x + 40, y + 40), 10)
        pygame.display.flip()
    def update_display(self, message):
        print(message)  # Simplified for console output
        self.screen.fill((255, 255, 255))
        self.draw_board()
        text = self.font.render(message, True, (0, 0, 0))
        self.screen.blit(text, (10, 500))
        pygame.display.flip()
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()