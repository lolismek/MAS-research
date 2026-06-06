'''
Represents a property on the board, including ownership and rent.
'''
class Property:
    def __init__(self, name, price, rent):
        self.name = name
        self.price = price
        self.rent = rent
        self.owner = None
    def buy(self, player):
        if player.money >= self.price:
            player.money -= self.price
            self.owner = player
    def calculate_rent(self):
        return self.rent