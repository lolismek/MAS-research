'''
Main entry point for the Checkers game application.
'''
import pygame
from game import Game
def main():
    pygame.init()
    screen = pygame.display.set_mode((800, 800))
    pygame.display.set_caption('Checkers Game')
    game = Game(screen)
    game.run()
    pygame.quit()
if __name__ == "__main__":
    main()