from dataclasses import dataclass
from fractions import Fraction

from center.cuts import Cuts


ZONE_ORDER = ('LL', 'HL', 'LH', 'HH')
ZONE_SIDES = tuple((zone[0] == 'H', zone[1] == 'H') for zone in ZONE_ORDER)


@dataclass(frozen=True)
class PartitionResult:
    cuts: Cuts
    masses: tuple[Fraction, Fraction, Fraction, Fraction]
