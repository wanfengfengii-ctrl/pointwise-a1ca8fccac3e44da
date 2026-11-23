from fractions import Fraction

from center.area_clip import clip_area_to_zone, polygon_area
from center.cuts import axis_side
from center.mass_check import require_conserved_mass
from center.partition_result import ZONE_ORDER, ZONE_SIDES, PartitionResult


def measure_line_unit(unit, cuts, x_high, y_high):
    start, end = unit.vertices
    lower = Fraction(0)
    upper = Fraction(1)
    for origin, finish, cut, high in zip(start, end, (cuts.x, cuts.y), (x_high, y_high)):
        delta = finish - origin
        if delta == 0:
            if axis_side(origin, cut) != high:
                return Fraction(0)
            continue
        crossing = (cut - origin) / delta
        # An isolated endpoint has zero line mass. A constant axis is handled above.
        if high == (delta > 0):
            lower = max(lower, crossing)
        else:
            upper = min(upper, crossing)
    if lower >= upper:
        return Fraction(0)

    mass = Fraction(0)
    for start_t, end_t, left, right in unit.density:
        begin = max(lower, start_t)
        finish = min(upper, end_t)
        if begin < finish:
            slope = (right - left) / (end_t - start_t)
            begin_rate = left + slope * (begin - start_t)
            finish_rate = left + slope * (finish - start_t)
            mass += (finish - begin) * (begin_rate + finish_rate) / 2
    return mass


def partition_mass(receipt, cuts):
    totals = [Fraction(0) for _ in ZONE_ORDER]
    for unit in receipt.units:
        if unit.kind == 'point':
            x, y = unit.vertices[0]
            zone = (axis_side(x, cuts.x), axis_side(y, cuts.y))
            totals[ZONE_SIDES.index(zone)] += unit.mass
        elif unit.kind == 'line':
            for index, sides in enumerate(ZONE_SIDES):
                totals[index] += measure_line_unit(unit, cuts, *sides)
        elif unit.kind == 'area':
            mass_per_area = unit.mass / polygon_area(unit.vertices)
            for index, sides in enumerate(ZONE_SIDES):
                totals[index] += mass_per_area * clip_area_to_zone(unit.vertices, cuts, *sides)
        else:
            raise ValueError(f'unsupported mass unit kind {unit.kind!r}')
    result = PartitionResult(cuts, tuple(totals))
    require_conserved_mass(result, receipt.total_mass)
    return result
