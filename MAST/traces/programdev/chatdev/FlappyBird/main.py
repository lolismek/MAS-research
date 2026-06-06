'''
Main file to initialize and run the Flappy Bird clone game using Pygame.
'''
import pygame
from game import Game
def main():
    pygame.init()
    game = Game()
    game.run()
if __name__ == "__main__":
    main()