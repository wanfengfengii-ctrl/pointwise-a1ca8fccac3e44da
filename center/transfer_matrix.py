from fractions import Fraction

from center.area_clip import polygon_area
from center.partition_result import ZONE_SIDES

# The joint evidence expresses each edition as the millimetre images of the
# three vertices of a normalized material simplex.  Area ratios inside the
# simplex equal area ratios on the source triangle, so the center can weigh
# transfers without ever seeing source coordinates or calibration parameters.
SIMPLEX = ((Fraction(0), Fraction(0)), (Fraction(1), Fraction(0)), (Fraction(0), Fraction(1)))
SIMPLEX_AREA = Fraction(1, 2)


def _clip_half_plane(vertices, alpha, beta, gamma, high):
    """Keep the side of ``alpha*x + beta*y + gamma`` selected by ``high``.

    Equality belongs to the high side, so a constant zero form keeps the whole
    polygon for the high side and nothing for the low side.  For nonconstant
    forms the boundary has zero area, so the low side may keep ``<= 0``.
    """
    if alpha == 0 and beta == 0:
        if high:
            return list(vertices) if gamma >= 0 else []
        return list(vertices) if gamma < 0 else []

    def value(point):
        return alpha * point[0] + beta * point[1] + gamma

    clipped = []
    previous = vertices[-1]
    previous_value = value(previous)
    previous_inside = previous_value >= 0 if high else previous_value <= 0
    for current in vertices:
        current_value = value(current)
        current_inside = current_value >= 0 if high else current_value <= 0
        if previous_inside != current_inside:
            fraction = previous_value / (previous_value - current_value)
            clipped.append(tuple(a + fraction * (b - a) for a, b in zip(previous, current)))
        if current_inside:
            clipped.append(current)
        previous, previous_value, previous_inside = current, current_value, current_inside
    return clipped


def _clip_edition(vertices, images, cuts, x_high, y_high):
    origin, x_step, y_step = images
    result = list(vertices)
    for axis, cut, keep_high in ((0, cuts.x, x_high), (1, cuts.y, y_high)):
        alpha = x_step[axis] - origin[axis]
        beta = y_step[axis] - origin[axis]
        gamma = origin[axis] - cut
        result = _clip_half_plane(result, alpha, beta, gamma, keep_high)
        if not result:
            break
    return result


def transfer_matrix(units, old_cuts, new_cuts):
    """Weigh the 4x4 transfer matrix, rows old zones and columns new zones."""
    matrix = [[Fraction(0) for _ in ZONE_SIDES] for _ in ZONE_SIDES]
    for unit in units:
        for old_index, (old_x_high, old_y_high) in enumerate(ZONE_SIDES):
            old_region = _clip_edition(SIMPLEX, unit.old, old_cuts, old_x_high, old_y_high)
            if not old_region:
                continue
            for new_index, (new_x_high, new_y_high) in enumerate(ZONE_SIDES):
                region = _clip_edition(old_region, unit.new, new_cuts, new_x_high, new_y_high)
                area = polygon_area(region)
                if area:
                    matrix[old_index][new_index] += unit.mass * area / SIMPLEX_AREA
    return matrix


def require_conserved_transfer(matrix, total_mass):
    if len(matrix) != 4 or any(len(row) != 4 for row in matrix):
        raise ValueError('transfer matrix must have four rows of four masses')
    if any(mass < 0 for row in matrix for mass in row):
        raise ValueError('transfer matrix must not contain negative masses')
    if sum((sum(row) for row in matrix), Fraction(0)) != total_mass:
        raise ValueError('transfer matrix mass does not match the pair total')
