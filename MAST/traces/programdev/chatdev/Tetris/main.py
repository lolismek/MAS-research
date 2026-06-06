'''
Main entry point for the Tetris game.
'''
import pygame
from game import Game
def main():
    pygame.init()
    game = Game()
    game.run()
    pygame.quit()
if __name__ == "__main__":
    main()