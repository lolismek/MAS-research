'''
Utility functions for the Checkers game.
'''
def position_to_coordinates(position):
    row, col = position
    return col * 100 + 50, row * 100 + 50
def coordinates_to_position(x, y):
    return y // 100, x // 100
def notation_to_coordinates(notation):
    '''
    Convert move notation (e.g., "A3-B4") to board coordinates.
    '''
    from_notation, to_notation = notation.split('-')
    from_pos = (8 - int(from_notation[1]), ord(from_notation[0].upper()) - ord('A'))
    to_pos = (8 - int(to_notation[1]), ord(to_notation[0].upper()) - ord('A'))
    return from_pos, to_pos