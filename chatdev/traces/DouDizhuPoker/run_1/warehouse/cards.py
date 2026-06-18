'''
Card utilities and deck creation for Dou Dizhu.
'''
from dataclasses import dataclass
from typing import List
RANK_ORDER = {
    "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14, "2": 15,
    "SJ": 16, "BJ": 17
}
SUITS = ["♠", "♥", "♦", "♣"]
@dataclass(frozen=True)
class Card:
    rank: str
    suit: str = ""
    @property
    def value(self) -> int:
        return RANK_ORDER[self.rank]
    def label(self) -> str:
        if self.rank in ("SJ", "BJ"):
            return self.rank
        return f"{self.rank}{self.suit}"
def create_deck() -> List[Card]:
    deck = [Card(rank, suit) for rank in [
        "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"
    ] for suit in SUITS]
    deck.append(Card("SJ", ""))
    deck.append(Card("BJ", ""))
    return deck
def card_sort_key(card: Card):
    return (card.value, card.suit)
def sort_cards(cards: List[Card]) -> List[Card]:
    return sorted(cards, key=card_sort_key)