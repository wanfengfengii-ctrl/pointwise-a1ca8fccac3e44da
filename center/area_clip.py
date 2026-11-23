from fractions import Fraction

from center.cuts import axis_side


def polygon_area(vertices):
    vertices = tuple(vertices)
    edges = zip(vertices, vertices[1:] + vertices[:1])
    double_area = sum((a[0] * b[1] - a[1] * b[0] for a, b in edges), Fraction(0))
    return abs(double_area) / 2


def _clip(vertices, axis, cut, high):
    if not vertices:
        return []
    clipped = []
    previous = vertices[-1]
    previous_inside = axis_side(previous[axis], cut) == high
    for current in vertices:
        inside = axis_side(current[axis], cut) == high
        if previous_inside != inside:
            t = (cut - previous[axis]) / (current[axis] - previous[axis])
            clipped.append(tuple(a + t * (b - a) for a, b in zip(previous, current)))
        if inside:
            clipped.append(current)
        previous = current
        previous_inside = inside
    return clipped


def clip_area_to_zone(vertices, cuts, x_high, y_high):
    x_clipped = _clip(vertices, 0, cuts.x, x_high)
    return polygon_area(_clip(x_clipped, 1, cuts.y, y_high))
