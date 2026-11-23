from fractions import Fraction

from center.partition_result import ZONE_ORDER, PartitionResult


def require_conserved_mass(result: PartitionResult, total_mass: Fraction):
    if len(result.masses) != len(ZONE_ORDER) or any(mass < 0 for mass in result.masses):
        raise ValueError('partition must contain four nonnegative masses')
    if sum(result.masses, Fraction(0)) != total_mass:
        raise ValueError('partition mass does not match the receipt total')
