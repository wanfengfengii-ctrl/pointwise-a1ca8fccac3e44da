from dataclasses import dataclass
from fractions import Fraction

from exact import rational


@dataclass(frozen=True)
class Cuts:
    x: Fraction
    y: Fraction


def parse_cuts(x_cut, y_cut):
    return Cuts(rational(x_cut, 'x cut'), rational(y_cut, 'y cut'))


def axis_side(coordinate, cut):
    # False is low. True is high, including equality.
    return coordinate >= cut
