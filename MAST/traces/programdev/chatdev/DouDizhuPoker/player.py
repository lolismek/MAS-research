'''
Player class to represent each player in the game.
'''
class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
        self.role = 'peasant'
    def add_card(self, card):
        self.hand.append(card)
    def set_role(self, role):
        self.role = role
    def play_card(self, card):
        if card in self.hand:
            self.hand.remove(card)
            return card
        return None