'''
Main file to run the Pong game.
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