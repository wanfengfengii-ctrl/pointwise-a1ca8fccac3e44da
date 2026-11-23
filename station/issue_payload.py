from dataclasses import dataclass
from fractions import Fraction

from exact import Point, canonical_json, sha256_text


DensitySpan = tuple[Fraction, Fraction, Fraction, Fraction]


@dataclass(frozen=True)
class MassUnit:
    kind: str
    vertices: tuple[Point, ...]
    mass: Fraction
    density: tuple[DensitySpan, ...] = ()


def encode_mass_body(units):
    records = []
    total = Fraction(0)
    for unit in units:
        record = {
            'kind': unit.kind,
            'vertices': [[str(x), str(y)] for x, y in unit.vertices],
            'mass': str(unit.mass),
        }
        if unit.kind == 'line':
            record['density'] = [[str(value) for value in span] for span in unit.density]
        records.append(record)
        total += unit.mass
    # Canonical order depends only on emitted evidence, not on station piece names.
    return {'total_mass': str(total), 'units': sorted(records, key=canonical_json)}


def encode_station_piece(station_id, issue_id, batch_id, revision_id, body):
    return canonical_json({
        'version': 1,
        'coordinate_unit': 'mm',
        'station_id': station_id,
        'issue_id': issue_id,
        'batch_id': batch_id,
        'revision_id': revision_id,
        'body_sha256': sha256_text(canonical_json(body)),
        'body': body,
    })
