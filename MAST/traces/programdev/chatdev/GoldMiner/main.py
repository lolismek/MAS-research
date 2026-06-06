'''
Main entry point for the Gold Miner game.
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