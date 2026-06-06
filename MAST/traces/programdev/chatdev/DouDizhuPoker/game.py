'''
Game class to manage the Dou Dizhu game flow.
'''
import pygame
from deck import Deck
from player import Player
from gui import GUI
from rules import is_valid_combination, can_beat
class Game:
    def __init__(self, screen):
        self.screen = screen
        self.deck = Deck()
        self.players = [Player(f'Player {i+1}') for i in range(3)]
        self.gui = GUI(screen, self.players)
        self.current_player_index = 0
        self.landlord = None
        self.current_combination = []
        self.passes = 0
    def run(self):
        self.deck.shuffle()
        self.deal_cards()
        self.bidding_phase()
        self.main_game_loop()
    def deal_cards(self):
        for _ in range(17):
            for player in self.players:
                player.add_card(self.deck.draw_card())
    def bidding_phase(self):
        highest_bid = 0
        landlord_candidate = None
        for i in range(len(self.players)):
            player = self.players[(self.current_player_index + i) % len(self.players)]
            bid = self.get_player_bid(player)
            if bid > highest_bid:
                highest_bid = bid
                landlord_candidate = player
        if landlord_candidate:
            self.landlord = landlord_candidate
            self.landlord.set_role('landlord')
            # Deal the remaining 3 cards to the landlord
            for _ in range(3):
                self.landlord.add_card(self.deck.draw_card())
    def get_player_bid(self, player):
        # Placeholder for actual player input logic
        import random
        # Simulate a bidding process with a chance to pass
        return random.choice([0, 1, 2, 3]) if random.random() > 0.5 else 0
    def main_game_loop(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            self.play_turn(self.players[self.current_player_index])
            if self.check_winner():
                running = False
            self.gui.update()
            pygame.display.flip()
    def play_turn(self, player):
        # Placeholder for player action logic
        # Simulate a random action: play a card or pass
        import random
        action = random.choice(['play', 'pass'])
        if action == 'play':
            # Simulate playing a random valid combination
            cards = player.hand[:1]  # Simplified: play the first card
            if is_valid_combination(cards) and (not self.current_combination or can_beat(self.current_combination, cards)):
                self.current_combination = cards
                for card in cards:
                    player.play_card(card)
                self.passes = 0
            else:
                self.passes += 1
        else:
            self.passes += 1
        if self.passes >= len(self.players) - 1:
            self.current_combination = []
            self.passes = 0
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
    def check_winner(self):
        for player in self.players:
            if not player.hand:
                print(f'{player.name} wins!')
                return True
        return False