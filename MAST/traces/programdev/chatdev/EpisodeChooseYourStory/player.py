'''
Defines the Player class for tracking player-related variables such as relationships and items.
'''
class Player:
    def __init__(self):
        self.relationships = {}
        self.inventory = []
    def update_relationship(self, character, value):
        if character in self.relationships:
            self.relationships[character] += value
        else:
            self.relationships[character] = value
    def add_item(self, item):
        self.inventory.append(item)