"""Grain market default layout and movement rules."""

BOURSE_GRID_SIZE = 7
BOURSE_GRID_VALUES = [6, 4, 2, 0, 2, 4, 6]

BOURSE_DEFAULT_POS = 3
BOURSE_BLOCK_MIN = 1
BOURSE_BLOCK_MAX = 5

BOURSE_SURCHARGE_FACTOR = 0.05

BOURSE_MOVEMENT_DIVISOR = 10
BOURSE_MIN_MOVEMENT = 1

BOURSE_GRAIN_LAYOUT = {
    (-1, -1): 'orge',
    (0, -1): 'triticale',
    (1, -1): 'ble',
    (-1, 0): None,
    (0, 0): 'mais',
    (1, 0): None,
    (-1, 1): 'seigle',
    (0, 1): None,
    (1, 1): 'avoine',
}
