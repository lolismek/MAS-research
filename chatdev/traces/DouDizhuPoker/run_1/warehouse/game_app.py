'''
Tkinter GUI application for Dou Dizhu.
'''
import tkinter as tk
from tkinter import messagebox
from game_state import GameState
from ai_player import choose_bid, choose_play
class DouDizhuApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dou Dizhu")
        self.root.geometry("1100x700")
        self.state = GameState()
        self.selected_indices = set()
        self.player_modes = ["human", "ai", "ai"]
        self.human_player_index = 0
        self._build_ui()
        self.new_game()
    def _build_ui(self):
        self.info_label = tk.Label(self.root, text="", font=("Arial", 14))
        self.info_label.pack(pady=8)
        self.table_label = tk.Label(self.root, text="", font=("Arial", 12), fg="blue")
        self.table_label.pack(pady=4)
        self.landlord_label = tk.Label(self.root, text="", font=("Arial", 12), fg="purple")
        self.landlord_label.pack(pady=4)
        self.hand_frame = tk.Frame(self.root)
        self.hand_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=15)
        self.center_frame = tk.Frame(self.root)
        self.center_frame.pack(side=tk.BOTTOM, pady=8)
        self.bid_frame = tk.Frame(self.root)
        self.bid_frame.pack(side=tk.TOP, pady=10)
        self.buttons = []
        for i in range(4):
            text = "Pass" if i == 0 else f"Bid {i}"
            btn = tk.Button(self.bid_frame, text=text, width=10,
                            command=lambda v=i: self.human_bid(v))
            btn.grid(row=0, column=i, padx=5)
            self.buttons.append(btn)
        self.pass_button = tk.Button(self.center_frame, text="Pass", width=12, command=self.human_pass)
        self.pass_button.grid(row=0, column=0, padx=5)
        self.play_button = tk.Button(self.center_frame, text="Play Selected", width=15, command=self.human_play)
        self.play_button.grid(row=0, column=1, padx=5)
        self.new_button = tk.Button(self.center_frame, text="New Game", width=12, command=self.new_game)
        self.new_button.grid(row=0, column=2, padx=5)
        self.cards_canvas = tk.Frame(self.root)
        self.cards_canvas.pack(fill=tk.BOTH, expand=True, pady=10)
    def new_game(self):
        self.state.start_new_game()
        self.selected_indices.clear()
        self._refresh()
        self.root.after(500, self._auto_bidding_loop)
    def _auto_bidding_loop(self):
        if not self.state.bidding_phase:
            self._refresh()
            self._maybe_ai_turn()
            return
        current = self.state.bidding_turn
        if self.player_modes[current] == "human":
            self._refresh()
            return
        bid = choose_bid(self.state, current)
        self.state.bid(current, bid)
        self._refresh()
        if self.state.bidding_phase:
            self.root.after(700, self._auto_bidding_loop)
        else:
            self._maybe_ai_turn()
    def human_bid(self, bid_value):
        if not self.state.bidding_phase:
            return
        if self.player_modes[self.state.bidding_turn] != "human":
            return
        self.state.bid(self.state.bidding_turn, bid_value)
        self._refresh()
        if self.state.bidding_phase:
            self.root.after(200, self._auto_bidding_loop)
        else:
            self._maybe_ai_turn()
    def human_pass(self):
        if self.state.bidding_phase or self.state.winner is not None:
            return
        if self.state.current_turn != self.human_player_index:
            return
        if self.state.pass_turn(self.human_player_index):
            self.selected_indices.clear()
            self._refresh()
            self._maybe_ai_turn()
    def human_play(self):
        if self.state.bidding_phase or self.state.winner is not None:
            return
        if self.state.current_turn != self.human_player_index:
            return
        hand = self.state.players[self.human_player_index]
        cards = [hand[i] for i in sorted(self.selected_indices)]
        if self.state.play_cards(self.human_player_index, cards):
            self.selected_indices.clear()
            self._refresh()
            self._maybe_ai_turn()
        else:
            messagebox.showerror("Invalid Move", "Selected cards do not form a valid playable combination.")
    def _maybe_ai_turn(self):
        if self.state.bidding_phase or self.state.winner is not None:
            self._refresh()
            return
        current = self.state.current_turn
        if self.player_modes[current] == "human":
            self._refresh()
            return
        self.root.after(700, self._ai_take_turn)
    def _ai_take_turn(self):
        if self.state.winner is not None or self.state.bidding_phase:
            self._refresh()
            return
        current = self.state.current_turn
        if self.player_modes[current] != "ai":
            self._refresh()
            return
        play = choose_play(self.state, current)
        if play is None:
            self.state.pass_turn(current)
        else:
            self.state.play_cards(current, play)
        self._refresh()
        if self.state.winner is None:
            self._maybe_ai_turn()
    def _card_button_command(self, idx):
        if idx in self.selected_indices:
            self.selected_indices.remove(idx)
        else:
            self.selected_indices.add(idx)
        self._refresh()
    def _refresh(self):
        self._render_info()
        self._render_table()
        self._render_hand()
        self._render_buttons_state()
    def _render_info(self):
        if self.state.winner is not None:
            winner_text = "Landlord" if self.state.winner == self.state.landlord_index else "Farmers"
            self.info_label.config(text=f"Game Over: Player {self.state.winner + 1} wins! ({winner_text})")
            return
        if self.state.bidding_phase:
            turn = self.state.bidding_turn
            self.info_label.config(text=f"Bidding phase. Player {turn + 1}'s turn.")
        else:
            self.info_label.config(text=f"Turn: Player {self.state.current_turn + 1}")
        if self.state.landlord_index is None:
            self.landlord_label.config(text="Landlord: not decided yet")
        else:
            self.landlord_label.config(text=f"Landlord: Player {self.state.landlord_index + 1}")
    def _render_table(self):
        if self.state.last_combo is None:
            self.table_label.config(text="Last play: none")
        else:
            desc = self.state.last_combo.description()
            cards = " ".join(card.label() for card in self.state.last_combo.cards)
            self.table_label.config(text=f"Last play: {desc} | {cards}")
    def _render_hand(self):
        for widget in self.cards_canvas.winfo_children():
            widget.destroy()
        if not self.state.players:
            return
        hand = self.state.players[self.human_player_index]
        for idx, card in enumerate(hand):
            selected = idx in self.selected_indices
            txt = card.label()
            if selected:
                txt = f"[{txt}]"
            btn = tk.Button(
                self.cards_canvas,
                text=txt,
                width=6,
                command=lambda i=idx: self._card_button_command(i),
                bg="#ffd966" if selected else "white"
            )
            btn.pack(side=tk.LEFT, padx=2)
    def _render_buttons_state(self):
        bidding = self.state.bidding_phase
        turn = self.state.bidding_turn if bidding else self.state.current_turn
        human_turn = (turn == self.human_player_index and self.player_modes[self.human_player_index] == "human")
        for btn in self.buttons:
            btn.config(state=tk.NORMAL if bidding and human_turn else tk.DISABLED)
        if self.state.bidding_phase:
            self.pass_button.config(state=tk.DISABLED)
            self.play_button.config(state=tk.DISABLED)
        else:
            self.pass_button.config(state=tk.NORMAL if human_turn and self.state.last_combo is not None else tk.DISABLED)
            self.play_button.config(state=tk.NORMAL if human_turn else tk.DISABLED)
def run_app():
    root = tk.Tk()
    app = DouDizhuApp(root)
    root.mainloop()