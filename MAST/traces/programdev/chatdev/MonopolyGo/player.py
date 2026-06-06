'''
Represents a player in the game, tracking their money, properties, and position.
'''
class Player:
    def __init__(self, name):
        self.name = name
        self.money = 1500
        self.position = 0
        self.properties = []
        self.in_jail = False
    def move(self, roll, board):
        if not self.in_jail:
            self.position = (self.position + roll) % len(board.spaces)
        else:
            self.in_jail = False  # Simplified rule to get out of jail
    def buy_property(self, property):
        if self.money >= property.price:
            self.money -= property.price
            self.properties.append(property)
            property.owner = self
    def pay_rent(self, amount):
        self.money -= amount
    def go_to_jail(self, board):
        self.in_jail = True
        self.position = board.jail_position
    def get_out_of_jail(self):
        self.in_jail = False