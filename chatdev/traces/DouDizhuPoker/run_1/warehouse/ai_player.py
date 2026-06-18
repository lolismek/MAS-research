'''
Simple AI bidding and playing logic.
'''
from typing import List, Optional, Tuple
from cards import Card, sort_cards
from combination import analyze_cards, can_beat, Combination, CombinationType
from game_state import GameState
def choose_bid(state: GameState, player_index: int) -> int:
    hand = state.players[player_index]
    strength = sum(card.value for card in hand)
    if any(card.rank in ("SJ", "BJ") for card in hand):
        strength += 20
    if any(card.value >= 15 for card in hand):
        strength += 10
    if strength > 190:
        return 3
    if strength > 175:
        return 2
    if strength > 160:
        return 1
    return 0
def _group_by_value(cards: List[Card]):
    groups = {}
    for c in cards:
        groups.setdefault(c.value, []).append(c)
    return groups
def _combo_rank(combo: Combination) -> Tuple[int, int, int]:
    order = {
        CombinationType.SINGLE: 1,
        CombinationType.PAIR: 2,
        CombinationType.TRIPLE: 3,
        CombinationType.TRIPLE_ONE: 4,
        CombinationType.TRIPLE_PAIR: 5,
        CombinationType.STRAIGHT: 6,
        CombinationType.PAIR_STRAIGHT: 7,
        CombinationType.TRIPLE_STRAIGHT: 8,
        CombinationType.BOMB: 9,
        CombinationType.ROCKET: 10,
    }
    return (order.get(combo.type, 0), combo.primary_value, combo.length)
def _find_play_from_candidates(candidates: List[List[Card]], last_combo: Optional[Combination]):
    valid = []
    for c in candidates:
        combo = analyze_cards(c)
        if combo and can_beat(combo, last_combo):
            valid.append((combo, c))
    if not valid:
        return None
    valid.sort(key=lambda x: _combo_rank(x[0]))
    return valid[0][1]
def _straight_candidates(values_to_cards, min_length=5):
    available_values = sorted(v for v in values_to_cards.keys() if v < 15)
    candidates = []
    i = 0
    while i < len(available_values):
        j = i
        while j + 1 < len(available_values) and available_values[j + 1] == available_values[j] + 1:
            j += 1
        seq = available_values[i:j + 1]
        for start in range(0, len(seq)):
            for end in range(start + min_length, len(seq) + 1):
                run = seq[start:end]
                candidates.append([values_to_cards[v][0] for v in run])
        i = j + 1
    return candidates
def choose_play(state: GameState, player_index: int) -> Optional[List[Card]]:
    hand = sort_cards(state.players[player_index])
    last_combo = state.last_combo
    groups = _group_by_value(hand)
    candidates: List[List[Card]] = []
    if last_combo is None:
        candidates.extend([[c] for c in hand])
        for _, g in groups.items():
            if len(g) >= 2:
                candidates.append(g[:2])
            if len(g) >= 3:
                candidates.append(g[:3])
            if len(g) >= 4:
                candidates.append(g[:4])
        if len(groups.get(16, [])) >= 1 and len(groups.get(17, [])) >= 1:
            candidates.append([groups[16][0], groups[17][0]])
        vals = {v: g for v, g in groups.items() if v < 15}
        candidates.extend(_straight_candidates(vals, 5))
        pair_vals = {v: g for v, g in groups.items() if v < 15 and len(g) >= 2}
        candidates.extend([[pair_vals[v][0], pair_vals[v][1]] for v in pair_vals])
        triple_vals = {v: g for v, g in groups.items() if v < 15 and len(g) >= 3}
        candidates.extend([[triple_vals[v][0], triple_vals[v][1], triple_vals[v][2]] for v in triple_vals])
        return _find_play_from_candidates(candidates, None) or ([hand[0]] if hand else None)
    if last_combo.type == CombinationType.SINGLE:
        candidates.extend([[c] for c in hand if c.value > last_combo.primary_value])
    elif last_combo.type == CombinationType.PAIR:
        for _, g in groups.items():
            if len(g) >= 2 and g[0].value > last_combo.primary_value:
                candidates.append(g[:2])
    elif last_combo.type == CombinationType.TRIPLE:
        for _, g in groups.items():
            if len(g) >= 3 and g[0].value > last_combo.primary_value:
                candidates.append(g[:3])
    elif last_combo.type == CombinationType.TRIPLE_ONE:
        for _, g in groups.items():
            if len(g) >= 3 and g[0].value > last_combo.primary_value:
                triple = g[:3]
                for s in hand:
                    if s.value != g[0].value:
                        candidates.append(triple + [s])
                        break
    elif last_combo.type == CombinationType.TRIPLE_PAIR:
        pairs = [g[:2] for _, g in groups.items() if len(g) >= 2]
        for _, g in groups.items():
            if len(g) >= 3 and g[0].value > last_combo.primary_value:
                triple = g[:3]
                for p in pairs:
                    if p[0].value != g[0].value:
                        candidates.append(triple + p)
                        break
    elif last_combo.type == CombinationType.BOMB:
        for _, g in groups.items():
            if len(g) >= 4 and g[0].value > last_combo.primary_value:
                candidates.append(g[:4])
    elif last_combo.type == CombinationType.STRAIGHT:
        needed = last_combo.length
        vals = sorted(v for v in groups.keys() if v < 15)
        for i in range(len(vals)):
            seq = vals[i:i + needed]
            if len(seq) == needed and seq[-1] > last_combo.primary_value and all(seq[k] + 1 == seq[k + 1] for k in range(len(seq) - 1)):
                candidates.append([groups[v][0] for v in seq])
    elif last_combo.type == CombinationType.PAIR_STRAIGHT:
        needed = last_combo.length
        vals = sorted(v for v in groups.keys() if v < 15 and len(groups[v]) >= 2)
        for i in range(len(vals)):
            seq = vals[i:i + needed]
            if len(seq) == needed and seq[-1] > last_combo.primary_value and all(seq[k] + 1 == seq[k + 1] for k in range(len(seq) - 1)):
                candidates.append([groups[v][0] for v in seq for _ in range(2)])
    elif last_combo.type == CombinationType.TRIPLE_STRAIGHT:
        needed = last_combo.length
        vals = sorted(v for v in groups.keys() if v < 15 and len(groups[v]) >= 3)
        for i in range(len(vals)):
            seq = vals[i:i + needed]
            if len(seq) == needed and seq[-1] > last_combo.primary_value and all(seq[k] + 1 == seq[k + 1] for k in range(len(seq) - 1)):
                candidates.append([groups[v][0] for v in seq for _ in range(3)])
    if last_combo.type not in (CombinationType.ROCKET,):
        if len(groups.get(16, [])) >= 1 and len(groups.get(17, [])) >= 1:
            candidates.append([groups[16][0], groups[17][0]])
    for _, g in groups.items():
        if len(g) >= 4:
            candidates.append(g[:4])
    play = _find_play_from_candidates(candidates, last_combo)
    if play:
        return play
    return None