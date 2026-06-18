'''
Core game logic for the simplified Monopoly Go-style game.
'''
import random
from typing import List, Tuple, Optional
from models import Player, Property, Space
from board import create_board
from chance import create_chance_cards, draw_random_card
class Game:
    def __init__(self, player_names: List[str]):
        """Initialize game state, board, chance deck, and player order."""
        self.players = [Player(name.strip()) for name in player_names if name.strip()]
        if len(self.players) < 2:
            raise ValueError("At least 2 players are required.")
        self.board = create_board()
        self.chance_cards = create_chance_cards()
        self.current_player_index = 0
        self.last_roll: Optional[Tuple[int, int]] = None
        self.last_message: str = ""
        self.game_over: bool = False
        self.winner: Optional[Player] = None
        # Turn state machine
        self.turn_phase: str = "start"  # start, rolled, decision
        self.has_rolled: bool = False
        self.can_buy: bool = False
        self.pending_property: Optional[Property] = None
        self.pending_message: str = ""
    @property
    def current_player(self) -> Player:
        """Return the player whose turn is currently active."""
        return self.players[self.current_player_index]
    def roll_dice(self) -> Tuple[int, int]:
        """Roll two six-sided dice."""
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        self.last_roll = (d1, d2)
        return d1, d2
    def transfer_money(self, payer: Optional[Player], payee: Optional[Player], amount: int) -> int:
        """
        Transfer money safely between players or to/from the bank.
        Returns the amount actually transferred.
        If a payer cannot fully cover the amount, they go bankrupt and pay all remaining cash.
        """
        if amount <= 0:
            return 0
        if payer is None and payee is not None:
            payee.add_money(amount)
            return amount
        if payee is None and payer is not None:
            paid = min(payer.money, amount)
            payer.remove_money(paid)
            if payer.money <= 0:
                self.handle_bankruptcy(payer, creditor=None)
            return paid
        if payer is None or payee is None:
            return 0
        paid = min(payer.money, amount)
        payer.remove_money(paid)
        payee.add_money(paid)
        if payer.money <= 0:
            self.handle_bankruptcy(payer, creditor=payee)
        return paid
    def handle_bankruptcy(self, player: Player, creditor: Optional[Player] = None) -> str:
        """
        Handle a player's bankruptcy by clearing owned properties and removing them from active play.
        """
        if not player.active:
            return f"{player.name} is already bankrupt."
        for prop in list(player.properties):
            prop.owner = creditor
            if creditor is None:
                player.remove_property(prop)
            else:
                creditor.add_property(prop)
                player.remove_property(prop)
        player.money = 0
        player.active = False
        player.in_jail = False
        player.jail_turns = 0
        if self.current_player == player:
            self.can_buy = False
            self.pending_property = None
        self._advance_past_inactive_players()
        self.check_winner()
        if creditor is not None:
            return f"{player.name} went bankrupt. Their properties were transferred to {creditor.name}."
        return f"{player.name} went bankrupt. Their properties returned to the bank."
    def move_player(self, player: Player, steps: int) -> str:
        """Move a player around the board and pay GO bonus when passing it."""
        old_pos = player.position
        new_pos = (player.position + steps) % len(self.board)
        if old_pos + steps >= len(self.board):
            player.add_money(200)
            go_msg = f"{player.name} passed GO and collected $200."
        else:
            go_msg = ""
        player.position = new_pos
        space = self.board[new_pos]
        return go_msg + (f" Landed on {space.name}." if go_msg else f"{player.name} moved to {space.name}.")
    def _reset_turn_actions(self) -> None:
        """Reset per-turn interaction flags."""
        self.has_rolled = False
        self.can_buy = False
        self.pending_property = None
        self.pending_message = ""
        self.turn_phase = "start"
    def _advance_past_inactive_players(self) -> None:
        """Move turn index forward until it points to an active player or the game ends."""
        if not any(p.active for p in self.players):
            self.game_over = True
            self.winner = None
            return
        start_index = self.current_player_index
        while not self.players[self.current_player_index].active:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            if self.current_player_index == start_index:
                break
    def _advance_to_next_player(self) -> None:
        """Advance current_player_index once, then skip inactive players."""
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self._advance_past_inactive_players()
    def start_turn(self) -> str:
        """Start the current player's turn and handle jail skip logic without recursion."""
        if self.game_over:
            return "The game is over."
        self._advance_past_inactive_players()
        if self.game_over:
            return "The game is over."
        player = self.current_player
        self._reset_turn_actions()
        if player.in_jail:
            player.jail_turns += 1
            if player.jail_turns >= 3:
                player.in_jail = False
                player.jail_turns = 0
                return f"{player.name} served 3 turns in jail and is released. Roll the dice now."
            self._advance_to_next_player()
            if self.game_over:
                return "The game is over."
            return f"{player.name} is in jail for turn {player.jail_turns}/3 and skips this turn."
        return f"It's {player.name}'s turn. Roll the dice."
    def roll_and_move(self) -> str:
        """Roll dice, move the active player, and resolve the landing space."""
        if self.game_over:
            return "The game is over."
        player = self.current_player
        if self.has_rolled:
            return "You have already rolled this turn. Choose buy/skip, then end the turn."
        if not player.active:
            return "This player is inactive."
        if player.in_jail:
            return f"{player.name} is in jail and cannot roll this turn."
        d1, d2 = self.roll_dice()
        steps = d1 + d2
        self.has_rolled = True
        self.turn_phase = "rolled"
        move_msg = self.move_player(player, steps)
        landing_msg = self.resolve_landing(player)
        self.check_winner()
        return f"Rolled {d1} and {d2} ({steps}). {move_msg} {landing_msg}".strip()
    def resolve_landing(self, player: Player) -> str:
        """Resolve the action for the space a player has landed on."""
        if not player.active:
            return ""
        space = self.board[player.position]
        self.can_buy = False
        self.pending_property = None
        if isinstance(space, Property):
            if space.owner is None:
                self.can_buy = True
                self.pending_property = space
                self.turn_phase = "decision"
                return f"{space.name} is unowned. You may buy it for ${space.cost} or skip."
            if space.owner is player:
                self.turn_phase = "decision"
                return f"You landed on your own property, {space.name}."
            rent = space.rent
            paid = self.transfer_money(player, space.owner, rent)
            self.turn_phase = "decision"
            if player.active:
                return f"{space.name} is owned by {space.owner.name}. Paid ${paid} rent."
            return f"{space.name} is owned by {space.owner.name}. {player.name} could only pay ${paid} and went bankrupt."
        if isinstance(space, Space):
            if space.space_type == "chance":
                card = draw_random_card(self.chance_cards)
                result = card.effect(self, player)
                self.turn_phase = "decision"
                self.check_winner()
                return f"Chance: {card.description}. {result}"
            if space.space_type == "go_to_jail":
                self.send_to_jail(player)
                self.turn_phase = "decision"
                return f"Go To Jail! {player.name} was sent to jail."
            if space.space_type == "free_parking":
                self.turn_phase = "decision"
                return f"{player.name} is resting at Free Parking. Nothing happens."
            if space.space_type == "jail":
                self.turn_phase = "decision"
                return f"{player.name} is just visiting Jail."
            if space.space_type == "go":
                self.turn_phase = "decision"
                return f"{player.name} is on GO."
        return ""
    def buy_property(self) -> str:
        """Buy the currently available unowned property, if affordable."""
        if self.game_over:
            return "Game over."
        player = self.current_player
        if not self.has_rolled:
            return "You must roll before buying."
        if not self.can_buy or self.pending_property is None:
            return "There is no property available to buy right now."
        space = self.pending_property
        if space.owner is not None:
            return "This property is already owned."
        if player.money < space.cost:
            self.handle_bankruptcy(player, creditor=None)
            return "You do not have enough money to buy this property and you went bankrupt."
        player.remove_money(space.cost)
        space.owner = player
        player.add_property(space)
        self.can_buy = False
        self.pending_property = None
        self.check_winner()
        return f"{player.name} bought {space.name} for ${space.cost}."
    def skip_purchase(self) -> str:
        """Skip buying the currently available property."""
        if self.game_over:
            return "Game over."
        if not self.has_rolled:
            return "You must roll before making a decision."
        self.can_buy = False
        self.pending_property = None
        return "Purchase skipped."
    def send_to_jail(self, player: Player) -> None:
        """Send a player to jail and reset their jail counter."""
        player.position = 6
        player.in_jail = True
        player.jail_turns = 0
    def end_turn(self, skip_validation: bool = False) -> str:
        """
        End the current turn and advance to the next active player.
        This method no longer calls start_turn() recursively.
        """
        if self.game_over:
            return "Game over."
        if not skip_validation and not self.has_rolled:
            return "Roll the dice before ending your turn."
        self._reset_turn_actions()
        self._advance_to_next_player()
        if self.game_over:
            return "The game is over."
        return f"Turn ended. Next player: {self.current_player.name}"
    def check_winner(self) -> Optional[Player]:
        """Check whether only one active player remains."""
        active = [p for p in self.players if p.active and p.money > 0]
        if len(active) == 1:
            self.game_over = True
            self.winner = active[0]
            return self.winner
        return None
    def player_status(self, player: Player) -> str:
        """Return a formatted one-line status string for a player."""
        props = ", ".join(p.name for p in player.properties) if player.properties else "None"
        jail = "Yes" if player.in_jail else "No"
        status = "Active" if player.active else "Bankrupt"
        return (
            f"{player.name}: Money=${player.money}, Pos={player.position}, "
            f"In Jail={jail}, Status={status}, Properties={props}"
        )
    def board_snapshot(self) -> List[str]:
        """Return a printable snapshot of the board state."""
        result = []
        for idx, space in enumerate(self.board):
            if isinstance(space, Property):
                owner = space.owner.name if space.owner else "Unowned"
                result.append(f"{idx}: {space.name} (${space.cost}, rent ${space.rent}) [{owner}]")
            else:
                result.append(f"{idx}: {space.name} ({space.space_type})")
        return result