'''
Rules module to enforce Dou Dizhu game rules.
'''
from collections import Counter
def is_valid_combination(cards):
    '''
    Check if the given cards form a valid Dou Dizhu combination.
    '''
    if not cards:
        return False
    card_counts = Counter(card.rank for card in cards)
    unique_counts = set(card_counts.values())
    # Single
    if len(cards) == 1:
        return True
    # Pair
    if len(cards) == 2 and len(unique_counts) == 1 and 2 in unique_counts:
        return True
    # Triple
    if len(cards) == 3 and len(unique_counts) == 1 and 3 in unique_counts:
        return True
    # Bomb (Four of a kind)
    if len(cards) == 4 and len(unique_counts) == 1 and 4 in unique_counts:
        return True
    # Straight (at least 5 cards)
    if len(cards) >= 5 and is_straight(card_counts):
        return True
    # Full House (Triple + Pair)
    if len(cards) == 5 and 3 in unique_counts and 2 in unique_counts:
        return True
    # Other combinations can be added here
    return False
def is_straight(card_counts):
    '''
    Check if the card counts form a straight.
    '''
    sorted_ranks = sorted(card_counts.keys())
    for i in range(len(sorted_ranks) - 1):
        if sorted_ranks[i + 1] - sorted_ranks[i] != 1:
            return False
    return True
def can_beat(current_combination, new_combination):
    '''
    Check if new_combination can beat current_combination.
    '''
    if not is_valid_combination(new_combination):
        return False
    if len(current_combination) != len(new_combination):
        return False
    current_counts = Counter(card.rank for card in current_combination)
    new_counts = Counter(card.rank for card in new_combination)
    # Compare based on the highest rank in the combination
    current_max = max(current_counts.keys())
    new_max = max(new_counts.keys())
    return new_max > current_max