'''
Deck class to manage the deck of cards.
'''
import random
from card import Card
class Deck:
    def __init__(self):
        self.cards = [Card(suit, rank) for suit in ['Hearts', 'Diamonds', 'Clubs', 'Spades'] for rank in range(1, 14)]
        self.cards += [Card('Joker', 14), Card('Joker', 15)]  # Assign integer ranks to Jokers
    def shuffle(self):
        random.shuffle(self.cards)
    def draw_card(self):
        return self.cards.pop() if self.cards else None