from fractions import Fraction

from exact import twice_signed_area
from station.batch_store import Batch
from station.calibration import map_vertices
from station.issue_payload import MassUnit
from station.revisions import Revision


def project_mass(vertices, mass):
    ordered = tuple(sorted(vertices))
    if twice_signed_area(ordered):
        return MassUnit('area', ordered, mass)
    start, middle, end = ordered
    if start == end:
        return MassUnit('point', (start,), mass)

    axis = 0 if start[0] != end[0] else 1
    knot = (middle[axis] - start[axis]) / (end[axis] - start[axis])
    zero = Fraction(0)
    one = Fraction(1)
    peak = 2 * mass
    spans = []
    # Below the middle image the original area grows quadratically with the
    # segment parameter. Above it the remaining area shrinks quadratically.
    if knot > zero:
        spans.append((zero, knot, zero, peak))
    if knot < one:
        spans.append((knot, one, peak, zero))
    return MassUnit('line', (start, end), mass, tuple(spans))


# Kept for callers of the original private name.
_project_mass = project_mass


def freeze_revision(batch: Batch, revision: Revision):
    if batch.id != revision.batch_id:
        raise ValueError('revision belongs to another batch')
    return tuple(
        project_mass(map_vertices(piece.triangle, revision.calibrations[piece.name]), piece.mass)
        for piece in batch.pieces
    )
