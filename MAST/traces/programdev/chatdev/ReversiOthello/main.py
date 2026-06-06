'''
Main entry point for the Reversi (Othello) game using Pygame.
'''
import pygame
from game import Game
def main():
    pygame.init()
    screen = pygame.display.set_mode((640, 640))
    pygame.display.set_caption('Reversi (Othello)')
    clock = pygame.time.Clock()
    game = Game(screen)
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                game.handle_click(event.pos)
        game.update()
        game.draw()
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()
if __name__ == '__main__':
    main()