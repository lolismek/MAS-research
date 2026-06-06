'''
Represents a chance card with various effects.
'''
import random
class ChanceCard:
    def __init__(self):
        self.effects = ["Go to Jail", "Collect $50", "Pay $50"]
    def draw_card(self):
        return random.choice(self.effects)
    def apply_effect(self, player, board):
        effect = self.draw_card()
        if effect == "Go to Jail":
            player.go_to_jail(board)
        elif effect == "Collect $50":
            player.money += 50
        elif effect == "Pay $50":
            player.money -= 50