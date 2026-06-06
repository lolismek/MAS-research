'''
Main entry point for the 2048 game application.
'''
import pygame
from game import Game
from gui import GUI
def main():
    pygame.init()
    game = Game()
    gui = GUI(game)
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            gui.handle_input(event)
        gui.update()
        pygame.display.flip()
        if game.is_game_over():
            print("Game Over! Your score:", game.score)
            running = False
    pygame.quit()
if __name__ == "__main__":
    main()