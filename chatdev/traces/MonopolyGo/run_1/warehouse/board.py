'''
Board creation utilities.
'''
from models import Space, Property
def create_board():
    """
    Create a simplified Monopoly-style board.
    Returns a list of spaces. Property spaces carry Property objects inside.
    """
    board = []
    board.append(Space("GO", "go"))
    board.append(Property("Brown Street", cost=60, rent=10))
    board.append(Space("Chance", "chance"))
    board.append(Property("Light Blue Ave", cost=100, rent=20))
    board.append(Space("Free Parking", "free_parking"))
    board.append(Property("Pink Plaza", cost=140, rent=28))
    board.append(Space("Jail", "jail"))
    board.append(Property("Orange Road", cost=180, rent=36))
    board.append(Space("Chance", "chance"))
    board.append(Property("Red Boulevard", cost=220, rent=44))
    board.append(Space("Go To Jail", "go_to_jail"))
    board.append(Property("Yellow Drive", cost=260, rent=52))
    board.append(Space("Chance", "chance"))
    board.append(Property("Green Garden", cost=300, rent=60))
    board.append(Space("Free Parking", "free_parking"))
    board.append(Property("Blue Estate", cost=350, rent=70))
    return board