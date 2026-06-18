'''
Tkinter GUI for the simplified Monopoly Go-style game.
This module now automatically falls back to a console interface when Tkinter
is unavailable, and it also avoids crashing in non-interactive environments
where stdin is not available.
'''
from __future__ import annotations
from typing import Optional
try:
    import tkinter as tk
    from tkinter import messagebox
    TK_AVAILABLE = True
except Exception:
    tk = None
    messagebox = None
    TK_AVAILABLE = False
from game import Game
from models import Property
class ConsoleMonopolyApp:
    """Fallback console UI for environments without Tkinter or stdin."""
    def __init__(self):
        self.game: Optional[Game] = None
    def _safe_input(self, prompt: str, default: str = "") -> str:
        """Read input safely; return default if stdin is unavailable."""
        try:
            return input(prompt).strip()
        except EOFError:
            return default
        except Exception:
            return default
    def run(self):
        print("Simplified Monopoly Go! (Console Mode)")
        raw = self._safe_input(
            "Enter player names separated by commas (min 2) [Alice, Bob]: ",
            default="",
        )
        if not raw:
            raw = "Alice, Bob"
        names = [n.strip() for n in raw.split(",")]
        try:
            self.game = Game(names)
        except ValueError as e:
            print(f"Error: {e}")
            return
        print(self.game.start_turn())
        while self.game and not self.game.game_over:
            player = self.game.current_player
            print("\n" + "-" * 60)
            print(f"Current player: {player.name}")
            print(self.game.player_status(player))
            print("Board:")
            for line in self.game.board_snapshot():
                print("  " + line)
            cmd = self._safe_input(
                "Choose: roll / buy / skip / end / status / quit: ",
                default="quit",
            ).lower()
            if cmd == "roll":
                print(self.game.roll_and_move())
            elif cmd == "buy":
                print(self.game.buy_property())
            elif cmd == "skip":
                print(self.game.skip_purchase())
            elif cmd == "end":
                print(self.game.end_turn())
                if not self.game.game_over:
                    print(self.game.start_turn())
            elif cmd == "status":
                for p in self.game.players:
                    print(self.game.player_status(p))
            elif cmd == "quit":
                print("Exiting game.")
                break
            else:
                print("Unknown command.")
            if self.game.game_over:
                break
        if self.game and self.game.winner:
            print(f"Game Over! Winner: {self.game.winner.name}")
if TK_AVAILABLE:
    class MonopolyGUI:
        """Tkinter GUI for the simplified Monopoly Go-style game."""
        def __init__(self):
            """Initialize the GUI and show the start screen."""
            self.root = tk.Tk()
            self.root.title("Simplified Monopoly Go!")
            self.root.geometry("1000x700")
            self.root.resizable(False, False)
            self.game = None
            self._build_start_screen()
        def _clear_root(self):
            """Remove all widgets from the root window."""
            for widget in self.root.winfo_children():
                widget.destroy()
        def _build_start_screen(self):
            """Create the initial screen for player name entry."""
            self._clear_root()
            frame = tk.Frame(self.root, padx=20, pady=20)
            frame.pack(fill="both", expand=True)
            title = tk.Label(frame, text="Simplified Monopoly Go!", font=("Arial", 24, "bold"))
            title.pack(pady=10)
            instructions = tk.Label(
                frame,
                text="Enter player names separated by commas (minimum 2 players).",
                font=("Arial", 12),
            )
            instructions.pack(pady=10)
            self.player_entry = tk.Entry(frame, width=60, font=("Arial", 12))
            self.player_entry.insert(0, "Alice, Bob")
            self.player_entry.pack(pady=10)
            start_btn = tk.Button(frame, text="Start Game", font=("Arial", 12, "bold"), command=self.start_game)
            start_btn.pack(pady=10)
        def start_game(self):
            """Create a new game instance from the entered player names."""
            names = [n.strip() for n in self.player_entry.get().split(",")]
            try:
                self.game = Game(names)
            except ValueError as e:
                messagebox.showerror("Error", str(e))
                return
            self._build_game_screen()
            self._refresh_ui()
            self._log(self.game.start_turn())
        def _build_game_screen(self):
            """Create the main game view."""
            self._clear_root()
            top_frame = tk.Frame(self.root)
            top_frame.pack(fill="x", padx=10, pady=5)
            self.turn_label = tk.Label(top_frame, text="", font=("Arial", 14, "bold"))
            self.turn_label.pack(side="left")
            self.roll_button = tk.Button(top_frame, text="Roll Dice", width=12, command=self.roll_dice)
            self.roll_button.pack(side="left", padx=5)
            self.buy_button = tk.Button(top_frame, text="Buy Property", width=12, command=self.buy_property)
            self.buy_button.pack(side="left", padx=5)
            self.skip_button = tk.Button(top_frame, text="Skip Buy", width=12, command=self.skip_buy)
            self.skip_button.pack(side="left", padx=5)
            self.end_button = tk.Button(top_frame, text="End Turn", width=12, command=self.end_turn)
            self.end_button.pack(side="left", padx=5)
            main_frame = tk.Frame(self.root)
            main_frame.pack(fill="both", expand=True, padx=10, pady=5)
            left_frame = tk.Frame(main_frame)
            left_frame.pack(side="left", fill="both", expand=True)
            right_frame = tk.Frame(main_frame, width=320)
            right_frame.pack(side="right", fill="y")
            board_label = tk.Label(left_frame, text="Board", font=("Arial", 14, "bold"))
            board_label.pack()
            self.board_listbox = tk.Listbox(left_frame, width=80, height=25, font=("Courier", 10))
            self.board_listbox.pack(fill="both", expand=True, pady=5)
            players_label = tk.Label(right_frame, text="Players", font=("Arial", 14, "bold"))
            players_label.pack()
            self.players_text = tk.Text(right_frame, width=38, height=16, font=("Courier", 10))
            self.players_text.pack(pady=5)
            log_label = tk.Label(right_frame, text="Game Log", font=("Arial", 14, "bold"))
            log_label.pack()
            self.log_text = tk.Text(right_frame, width=38, height=14, font=("Courier", 10))
            self.log_text.pack(pady=5)
        def _refresh_ui(self):
            """Refresh the board, player list, and button states."""
            if not self.game:
                return
            self.turn_label.config(text=f"Current Turn: {self.game.current_player.name}")
            self.board_listbox.delete(0, tk.END)
            for idx, space in enumerate(self.game.board):
                marker = ""
                for p in self.game.players:
                    if p.active and p.position == idx:
                        marker += f" <- {p.name}"
                if isinstance(space, Property):
                    owner = space.owner.name if space.owner else "Unowned"
                    line = f"{idx:02d} | {space.name:18} | Cost ${space.cost:<4} Rent ${space.rent:<4} | {owner}{marker}"
                else:
                    line = f"{idx:02d} | {space.name:18} | {space.space_type}{marker}"
                self.board_listbox.insert(tk.END, line)
            self.players_text.delete("1.0", tk.END)
            for player in self.game.players:
                self.players_text.insert(tk.END, self.game.player_status(player) + "\n")
            self._update_button_states()
            self._check_game_over()
        def _update_button_states(self):
            """Enable or disable buttons based on the current game state."""
            if not self.game:
                return
            if self.game.game_over:
                self.roll_button.config(state="disabled")
                self.buy_button.config(state="disabled")
                self.skip_button.config(state="disabled")
                self.end_button.config(state="disabled")
                return
            player = self.game.current_player
            if not player.active:
                self.roll_button.config(state="disabled")
                self.buy_button.config(state="disabled")
                self.skip_button.config(state="disabled")
                self.end_button.config(state="normal")
                return
            if player.in_jail:
                self.roll_button.config(state="disabled")
                self.buy_button.config(state="disabled")
                self.skip_button.config(state="disabled")
                self.end_button.config(state="normal")
                return
            self.roll_button.config(state="disabled" if self.game.has_rolled else "normal")
            self.buy_button.config(state="normal" if self.game.can_buy else "disabled")
            self.skip_button.config(state="normal" if self.game.has_rolled and self.game.can_buy else "disabled")
            self.end_button.config(state="normal" if self.game.has_rolled and not self.game.can_buy else "disabled")
        def _log(self, message: str):
            """Append a message to the game log."""
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
        def roll_dice(self):
            """Handle the Roll Dice button."""
            if not self.game or self.game.game_over:
                return
            msg = self.game.roll_and_move()
            self._log(msg)
            self._refresh_ui()
        def buy_property(self):
            """Handle the Buy Property button."""
            if not self.game or self.game.game_over:
                return
            result = self.game.buy_property()
            self._log(result)
            self._refresh_ui()
        def skip_buy(self):
            """Handle the Skip Buy button."""
            if not self.game or self.game.game_over:
                return
            result = self.game.skip_purchase()
            self._log(result)
            self._refresh_ui()
        def end_turn(self):
            """Handle the End Turn button."""
            if not self.game or self.game.game_over:
                return
            if self.game.can_buy:
                self._log("You must buy or skip the available property before ending the turn.")
                return
            result = self.game.end_turn()
            self._log(result)
            if self.game and not self.game.game_over:
                start_msg = self.game.start_turn()
                self._log(start_msg)
            self._refresh_ui()
        def _check_game_over(self):
            """Show a game-over popup once a winner has been determined."""
            if self.game and self.game.game_over:
                winner = self.game.winner.name if self.game.winner else "Unknown"
                messagebox.showinfo("Game Over", f"Game Over! Winner: {winner}")
                self.roll_button.config(state="disabled")
                self.buy_button.config(state="disabled")
                self.skip_button.config(state="disabled")
                self.end_button.config(state="disabled")
        def run(self):
            """Start the Tkinter main loop."""
            self.root.mainloop()
else:
    MonopolyGUI = ConsoleMonopolyApp