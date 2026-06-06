'''
GUI class to handle the graphical interface of the game.
'''
import pygame
class GUI:
    def __init__(self, screen, players):
        self.screen = screen
        self.players = players
    def update(self):
        self.screen.fill((0, 128, 0))  # Green background
        # Display players and their hands
        for i, player in enumerate(self.players):
            self.display_player(player, i)
    def display_player(self, player, index):
        font = pygame.font.Font(None, 36)
        text = font.render(f'{player.name}: {len(player.hand)} cards', True, (255, 255, 255))
        self.screen.blit(text, (50, 50 + index * 50))