'''
Data models used by the simplified Monopoly Go-style game.
'''
from dataclasses import dataclass, field
from typing import Optional, Callable, List
@dataclass
class Player:
    name: str
    money: int = 1500
    position: int = 0
    in_jail: bool = False
    jail_turns: int = 0
    active: bool = True
    properties: List["Property"] = field(default_factory=list)
    def add_property(self, prop: "Property") -> None:
        """Add a property to the player's inventory."""
        self.properties.append(prop)
    def remove_property(self, prop: "Property") -> None:
        """Remove a property from the player's inventory if owned."""
        if prop in self.properties:
            self.properties.remove(prop)
    def remove_money(self, amount: int) -> None:
        """Subtract money from the player without clamping."""
        self.money -= amount
    def add_money(self, amount: int) -> None:
        """Add money to the player."""
        self.money += amount
@dataclass
class Property:
    name: str
    cost: int
    rent: int
    owner: Optional[Player] = None
@dataclass
class Space:
    name: str
    space_type: str  # go, property, chance, jail, free_parking, go_to_jail, tax
@dataclass
class ChanceCard:
    description: str
    effect: Callable[["Game", Player], str]