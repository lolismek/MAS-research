'''
Combination parsing and comparison logic for Dou Dizhu.
'''
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from collections import Counter
from cards import Card, sort_cards
class CombinationType(str, Enum):
    INVALID = "invalid"
    SINGLE = "single"
    PAIR = "pair"
    TRIPLE = "triple"
    STRAIGHT = "straight"
    PAIR_STRAIGHT = "pair_straight"
    TRIPLE_STRAIGHT = "triple_straight"
    BOMB = "bomb"
    ROCKET = "rocket"
    TRIPLE_ONE = "triple_one"
    TRIPLE_PAIR = "triple_pair"
@dataclass
class Combination:
    type: CombinationType
    cards: List[Card]
    primary_value: int
    length: int = 1
    def description(self) -> str:
        return self.type.value.replace("_", " ").title()
def _is_consecutive(values: List[int]) -> bool:
    return all(values[i] + 1 == values[i + 1] for i in range(len(values) - 1))
def analyze_cards(cards: List[Card]) -> Optional[Combination]:
    if not cards:
        return None
    cards = sort_cards(cards)
    values = [c.value for c in cards]
    count = Counter(values)
    unique = sorted(count.keys())
    n = len(cards)
    if n == 1:
        return Combination(CombinationType.SINGLE, cards, values[0], 1)
    if n == 2:
        if set(values) == {16, 17}:
            return Combination(CombinationType.ROCKET, cards, 17, 1)
        if len(count) == 1:
            return Combination(CombinationType.PAIR, cards, values[0], 1)
        return None
    if n == 3:
        if len(count) == 1:
            return Combination(CombinationType.TRIPLE, cards, values[0], 1)
        return None
    if n == 4:
        if len(count) == 1:
            return Combination(CombinationType.BOMB, cards, values[0], 1)
        if sorted(count.values()) == [1, 3]:
            triple_val = max(count, key=lambda k: count[k])
            return Combination(CombinationType.TRIPLE_ONE, cards, triple_val, 1)
        return None
    if n == 5:
        if len(count) == 2 and sorted(count.values()) == [2, 3]:
            triple_val = max(count, key=lambda k: count[k])
            return Combination(CombinationType.TRIPLE_PAIR, cards, triple_val, 1)
        if all(v < 15 for v in unique) and len(count) == 5 and _is_consecutive(unique):
            return Combination(CombinationType.STRAIGHT, cards, max(unique), 5)
        return None
    if all(v < 15 for v in unique) and len(count) == n and _is_consecutive(unique):
        return Combination(CombinationType.STRAIGHT, cards, max(unique), n)
    if n % 2 == 0 and all(v < 15 for v in unique):
        if all(c == 2 for c in count.values()) and len(count) == n // 2 and _is_consecutive(unique):
            return Combination(CombinationType.PAIR_STRAIGHT, cards, max(unique), n // 2)
    if n % 3 == 0 and all(v < 15 for v in unique):
        if all(c == 3 for c in count.values()) and len(count) == n // 3 and _is_consecutive(unique):
            return Combination(CombinationType.TRIPLE_STRAIGHT, cards, max(unique), n // 3)
    return None
def can_beat(new_combo: Combination, last_combo: Optional[Combination]) -> bool:
    if last_combo is None:
        return True
    if new_combo.type == CombinationType.ROCKET:
        return True
    if last_combo.type == CombinationType.ROCKET:
        return False
    if new_combo.type == CombinationType.BOMB and last_combo.type != CombinationType.BOMB:
        return True
    if new_combo.type == CombinationType.BOMB and last_combo.type == CombinationType.BOMB:
        return new_combo.primary_value > last_combo.primary_value
    if last_combo.type == CombinationType.BOMB and new_combo.type != CombinationType.BOMB:
        return False
    if new_combo.type != last_combo.type:
        return False
    if new_combo.type in (CombinationType.STRAIGHT, CombinationType.PAIR_STRAIGHT, CombinationType.TRIPLE_STRAIGHT):
        return new_combo.length == last_combo.length and new_combo.primary_value > last_combo.primary_value
    return new_combo.length == last_combo.length and new_combo.primary_value > last_combo.primary_value