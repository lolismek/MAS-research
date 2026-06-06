'''
Manages the overall game flow, including turns, player actions, and game state.
'''
from player import Player
from board import Board
from gui import GUI
from dice import Dice
class Game:
    def __init__(self):
        self.players = [Player("Player 1"), Player("Player 2")]
        self.board = Board()
        self.gui = GUI(self.board, self.players)
        self.dice = Dice()
        self.current_player_index = 0
    def start_game(self):
        self.gui.draw_board()
        while not self.is_game_over():
            self.next_turn()
        self.end_game()
    def next_turn(self):
        player = self.players[self.current_player_index]
        self.gui.update_display(f"{player.name}'s turn")
        roll = self.dice.roll()
        player.move(roll, self.board)
        self.board.land_on_space(player)
        self.gui.update_display(f"{player.name} rolled a {roll}")
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
    def is_game_over(self):
        # Check if any player is truly bankrupt
        for player in self.players:
            if player.money < 0 and not player.properties:
                return True
        return False
    def end_game(self):
        self.gui.update_display("Game Over")