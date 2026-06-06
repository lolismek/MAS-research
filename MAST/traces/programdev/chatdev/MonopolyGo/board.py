'''
Represents the game board, including properties and special spaces.
'''
from property import Property
from chance_card import ChanceCard
class Board:
    def __init__(self):
        self.spaces = [Property("Mediterranean Avenue", 60, 2), ChanceCard(), Property("Baltic Avenue", 60, 4)]
        self.jail_position = 10
    def get_space_info(self, position):
        return self.spaces[position]
    def land_on_space(self, player):
        space = self.get_space_info(player.position)
        if isinstance(space, Property):
            if space.owner and space.owner != player:
                rent = space.calculate_rent()
                player.pay_rent(rent)
                space.owner.money += rent
            elif not space.owner:
                player.buy_property(space)
        elif isinstance(space, ChanceCard):
            space.apply_effect(player, self)