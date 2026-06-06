'''
Game class to manage the overall game state and loop.
'''
import pygame
from board import Board
from player import Player
from utils import notation_to_coordinates
class Game:
    def __init__(self, screen):
        self.screen = screen
        self.board = Board()
        self.players = [Player('white'), Player('black')]
        self.current_turn = 0
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            # Prompt for move notation
            move_notation = input("Enter your move (e.g., A3-B4): ")
            try:
                from_pos, to_pos = notation_to_coordinates(move_notation)
                if self.players[self.current_turn].make_move(self.board, from_pos, to_pos):
                    self.current_turn = (self.current_turn + 1) % 2
            except Exception as e:
                print(f"Invalid move: {e}")
            self.board.draw(self.screen)
            pygame.display.flip()