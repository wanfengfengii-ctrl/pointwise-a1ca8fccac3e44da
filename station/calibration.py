from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from exact import rational
from station.mesh import SourceTriangle


Coefficients = tuple[Fraction, Fraction, Fraction]


@dataclass(frozen=True)
class AffineCalibration:
    x: Coefficients
    y: Coefficients


def _coefficients(values):
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise ValueError('each affine row requires three coefficients')
    return tuple(rational(value, 'affine coefficient') for value in values)


def validate_calibration(calibrations, piece_names):
    if not isinstance(calibrations, Mapping) or set(calibrations) != set(piece_names):
        raise ValueError('calibration must cover exactly the pieces in the batch')
    result = {}
    for name, rows in calibrations.items():
        if not isinstance(rows, (list, tuple)) or len(rows) != 2:
            raise ValueError(f'piece {name!r} requires two affine rows')
        result[name] = AffineCalibration(_coefficients(rows[0]), _coefficients(rows[1]))
    return result


def map_vertices(triangle: SourceTriangle, calibration: AffineCalibration):
    a, b, c = calibration.x
    d, e, f = calibration.y
    return tuple((a * x + b * y + c, d * x + e * y + f) for x, y in triangle.vertices)
