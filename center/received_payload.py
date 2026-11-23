from dataclasses import dataclass
from fractions import Fraction

from exact import Point, canonical_json, load_json, twice_signed_area, wire_rational


@dataclass(frozen=True)
class ReceivedMassUnit:
    kind: str
    vertices: tuple[Point, ...]
    mass: Fraction
    density: tuple[tuple[Fraction, Fraction, Fraction, Fraction], ...]


@dataclass(frozen=True)
class DecodedStationPiece:
    station_id: str
    issue_id: int
    batch_id: int
    revision_id: int
    body_sha256: str
    body: str


def _decode_density(raw, mass):
    if not isinstance(raw, list) or not raw:
        raise ValueError('line density requires at least one span')
    spans = []
    cursor = Fraction(0)
    integral = Fraction(0)
    for row in raw:
        if not isinstance(row, list) or len(row) != 4:
            raise ValueError('density span requires two bounds and two endpoint rates')
        start, end, left, right = (wire_rational(value) for value in row)
        if start != cursor or not start < end <= 1 or min(left, right) < 0:
            raise ValueError('invalid density span bounds or rates')
        spans.append((start, end, left, right))
        integral += (end - start) * (left + right) / 2
        cursor = end
    if cursor != 1 or integral != mass:
        raise ValueError('density must cover the segment and integrate to its stated mass')
    return tuple(spans)


def _decode_unit(raw):
    if not isinstance(raw, dict):
        raise ValueError('mass unit must be an object')
    kind = raw.get('kind')
    if kind not in ('point', 'line', 'area'):
        raise ValueError('unknown mass unit kind')
    fields = {'kind', 'vertices', 'mass'}
    if kind == 'line':
        fields.add('density')
    if raw.keys() != fields:
        raise ValueError('wrong fields for mass unit')
    mass = wire_rational(raw['mass'])
    if mass <= 0:
        raise ValueError('mass unit must have positive mass')
    raw_vertices = raw['vertices']
    vertex_count = {'point': 1, 'line': 2, 'area': 3}[kind]
    if not isinstance(raw_vertices, list) or len(raw_vertices) != vertex_count:
        raise ValueError('wrong number of mass unit vertices')
    vertices = []
    for vertex in raw_vertices:
        if not isinstance(vertex, list) or len(vertex) != 2:
            raise ValueError('a millimeter vertex requires two coordinates')
        vertices.append((wire_rational(vertex[0]), wire_rational(vertex[1])))
    density = ()
    if kind == 'area' and twice_signed_area(vertices) == 0:
        raise ValueError('area unit must have nonzero area')
    if kind == 'line':
        if vertices[0] >= vertices[1]:
            raise ValueError('line endpoints must be distinct and lexically increasing')
        density = _decode_density(raw['density'], mass)
    return ReceivedMassUnit(kind, tuple(vertices), mass, density)


def decode_mass_body(body):
    if not isinstance(body, dict) or body.keys() != {'units', 'total_mass'}:
        raise ValueError('invalid mass body')
    raw_units = body['units']
    if not isinstance(raw_units, list) or not raw_units:
        raise ValueError('mass body requires at least one unit')
    units = tuple(_decode_unit(record) for record in raw_units)
    total_mass = wire_rational(body['total_mass'])
    if sum((unit.mass for unit in units), Fraction(0)) != total_mass:
        raise ValueError('mass body total does not match its units')
    return total_mass, units


def decode_station_piece(payload):
    data = load_json(payload)
    fields = {'version', 'coordinate_unit', 'station_id', 'issue_id', 'batch_id', 'revision_id',
              'body_sha256', 'body'}
    if not isinstance(data, dict) or data.keys() != fields:
        raise ValueError('invalid station piece envelope')
    if type(data['version']) is not int or data['version'] != 1 or data['coordinate_unit'] != 'mm':
        raise ValueError('unsupported station piece version or coordinate unit')
    decode_mass_body(data['body'])
    return DecodedStationPiece(data['station_id'], data['issue_id'], data['batch_id'],
                               data['revision_id'], data['body_sha256'], canonical_json(data['body']))
