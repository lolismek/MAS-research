'''
Game state and core Dou Dizhu rules.
'''
import random
from typing import List, Optional
from cards import Card, create_deck, sort_cards
from combination import Combination, analyze_cards, can_beat
class GameState:
    def __init__(self):
        self.players: List[List[Card]] = [[], [], []]
        self.bottom_cards: List[Card] = []
        self.landlord_index: Optional[int] = None
        self.current_turn: int = 0
        self.last_combo: Optional[Combination] = None
        self.last_player: Optional[int] = None
        self.pass_count: int = 0
        self.bidding_phase: bool = True
        self.bidding_turn: int = 0
        self.bids_in_round: int = 0
        self.highest_bid: int = 0
        self.highest_bidder: Optional[int] = None
        self.bid_history: List[Optional[int]] = [None, None, None]
        self.winner: Optional[int] = None
        self._landlord_finalized: bool = False
    def start_new_game(self):
        deck = create_deck()
        random.shuffle(deck)
        self.players = [sort_cards(deck[i * 17:(i + 1) * 17]) for i in range(3)]
        self.bottom_cards = sort_cards(deck[51:])
        self.landlord_index = None
        self.current_turn = 0
        self.last_combo = None
        self.last_player = None
        self.pass_count = 0
        self.bidding_phase = True
        self.bidding_turn = 0
        self.bids_in_round = 0
        self.highest_bid = 0
        self.highest_bidder = None
        self.bid_history = [None, None, None]
        self.winner = None
        self._landlord_finalized = False
    def bid(self, player_index: int, bid_value: int):
        """
        Process a bid during the landlord bidding phase.
        Rules implemented:
        - Players bid in turn order.
        - bid_value is 0..3, where 0 means pass.
        - A bid of 3 immediately finalizes landlord.
        - Otherwise, after all 3 players have bid once,
          the highest positive bid becomes landlord.
        - If all 3 players pass, a new bidding round starts from player 0.
        """
        if not self.bidding_phase or self._landlord_finalized:
            return False
        if player_index != self.bidding_turn:
            return False
        if bid_value < 0 or bid_value > 3:
            return False
        self.bid_history[player_index] = bid_value
        self.bids_in_round += 1
        if bid_value > self.highest_bid:
            self.highest_bid = bid_value
            self.highest_bidder = player_index
        self.bidding_turn = (self.bidding_turn + 1) % 3
        if bid_value == 3:
            self._finalize_landlord()
            return True
        if self.bids_in_round >= 3:
            if self.highest_bidder is not None and self.highest_bid > 0:
                self._finalize_landlord()
                return True
            if all(b == 0 for b in self.bid_history):
                self._reset_bidding_round()
                return True
            self._reset_bidding_round()
        return True
    def _reset_bidding_round(self):
        self.bids_in_round = 0
        self.highest_bid = 0
        self.highest_bidder = None
        self.bid_history = [None, None, None]
        self.bidding_turn = 0
    def _finalize_landlord(self):
        """
        Finalize landlord selection exactly once and distribute the three bottom cards.
        """
        if self._landlord_finalized:
            return
        if self.highest_bidder is None:
            self.highest_bidder = 0
        self.landlord_index = self.highest_bidder
        self.players[self.landlord_index].extend(self.bottom_cards)
        self.players[self.landlord_index] = sort_cards(self.players[self.landlord_index])
        self.current_turn = self.landlord_index
        self.bidding_phase = False
        self.last_combo = None
        self.last_player = None
        self.pass_count = 0
        self._landlord_finalized = True
    def play_cards(self, player_index: int, cards: List[Card]) -> bool:
        if self.bidding_phase or self.winner is not None:
            return False
        if player_index != self.current_turn:
            return False
        combo = analyze_cards(cards)
        if combo is None:
            return False
        if not can_beat(combo, self.last_combo):
            return False
        hand = self.players[player_index]
        for card in cards:
            if card not in hand:
                return False
        for card in cards:
            hand.remove(card)
        self.last_combo = combo
        self.last_player = player_index
        self.pass_count = 0
        self.current_turn = (self.current_turn + 1) % 3
        if len(hand) == 0:
            self.winner = player_index
        return True
    def pass_turn(self, player_index: int) -> bool:
        if self.bidding_phase or self.winner is not None:
            return False
        if player_index != self.current_turn:
            return False
        if self.last_combo is None:
            return False
        self.pass_count += 1
        self.current_turn = (self.current_turn + 1) % 3
        if self.pass_count >= 2 and self.last_player is not None:
            self.current_turn = self.last_player
            self.last_combo = None
            self.pass_count = 0
        return True