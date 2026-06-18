'''
Chance card definitions for the simplified Monopoly game.
'''
import random
from models import ChanceCard
def create_chance_cards():
    """
    Build the simplified chance card deck.
    Each card returns a message string after effect is applied.
    """
    cards = []
    def collect_50(game, player):
        game.transfer_money(None, player, 50)
        return f"{player.name} found a reward and collected $50."
    def pay_50(game, player):
        paid = game.transfer_money(player, None, 50)
        if paid < 50 and not player.active:
            return f"{player.name} could not pay the full $50 and went bankrupt."
        return f"{player.name} paid a $50 surprise fee."
    def go_to_go(game, player):
        player.position = 0
        player.add_money(200)
        return f"{player.name} moved to GO and collected $200."
    def go_to_jail(game, player):
        game.send_to_jail(player)
        return f"{player.name} was sent to Jail!"
    def collect_from_each(game, player):
        total = 0
        for p in game.players:
            if p is not player and p.active:
                paid = game.transfer_money(p, player, 25)
                total += paid
        return f"{player.name} collected ${total} from each other player."
    def pay_each(game, player):
        total_paid = 0
        for p in game.players:
            if p is not player and p.active:
                paid = game.transfer_money(player, p, 15)
                total_paid += paid
                if not player.active:
                    break
        if not player.active:
            return f"{player.name} could not afford to pay everyone and went bankrupt after paying ${total_paid}."
        return f"{player.name} paid ${total_paid} total to the other players."
    cards.append(ChanceCard("Collect $50", collect_50))
    cards.append(ChanceCard("Pay $50", pay_50))
    cards.append(ChanceCard("Advance to GO", go_to_go))
    cards.append(ChanceCard("Go to Jail", go_to_jail))
    cards.append(ChanceCard("Collect $25 from each player", collect_from_each))
    cards.append(ChanceCard("Pay $15 to each player", pay_each))
    return cards
def draw_random_card(cards):
    return random.choice(cards)