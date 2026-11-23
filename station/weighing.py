from exact import rational


def positive_mass(value):
    mass = rational(value, 'piece mass')
    if mass <= 0:
        raise ValueError('piece mass must be positive')
    return mass
