import re
from dataclasses import dataclass
from fractions import Fraction

from center.provenance import IssueProvenance
from exact import Point, canonical_json, load_json, require_id, require_station_id, sha256_text, wire_rational
from station.freeze import project_mass
from station.issue_payload import encode_mass_body


_DIGEST = re.compile('[0-9a-f]{64}')
_PARENT_FIELDS = {'station_id', 'issue_id', 'batch_id', 'revision_id', 'body_sha256'}


@dataclass(frozen=True)
class JointUnit:
    mass: Fraction
    old: tuple[Point, Point, Point]
    new: tuple[Point, Point, Point]


@dataclass(frozen=True)
class DecodedPairPiece:
    parents: tuple[IssueProvenance, IssueProvenance]
    body: str
    total_mass: Fraction
    units: tuple[JointUnit, ...]
    payload: str


def _decode_point(raw):
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError('a millimeter point requires two coordinates')
    return wire_rational(raw[0]), wire_rational(raw[1])


def decode_joint_body(body):
    if not isinstance(body, dict) or body.keys() != {'total_mass', 'units'}:
        raise ValueError('invalid joint evidence body')
    raw_units = body['units']
    if not isinstance(raw_units, list) or not raw_units:
        raise ValueError('joint evidence requires at least one unit')
    units = []
    total = Fraction(0)
    for raw in raw_units:
        if not isinstance(raw, dict) or raw.keys() != {'mass', 'old', 'new'}:
            raise ValueError('invalid joint evidence unit')
        mass = wire_rational(raw['mass'])
        if mass <= 0:
            raise ValueError('joint unit must have positive mass')
        images = {}
        for edition in ('old', 'new'):
            points = raw[edition]
            if not isinstance(points, list) or len(points) != 3:
                raise ValueError('a joint unit requires three image points per edition')
            images[edition] = tuple(_decode_point(point) for point in points)
        units.append(JointUnit(mass, images['old'], images['new']))
        total += mass
    if wire_rational(body['total_mass']) != total:
        raise ValueError('joint evidence total does not match its units')
    return total, tuple(units)


def _decode_parent(raw):
    if not isinstance(raw, dict) or raw.keys() != _PARENT_FIELDS:
        raise ValueError('invalid pair parent reference')
    digest = raw['body_sha256']
    if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
        raise ValueError('invalid pair parent digest')
    return IssueProvenance(
        require_station_id(raw['station_id']),
        require_id(raw['issue_id'], 'issue id'),
        require_id(raw['batch_id'], 'batch id'),
        require_id(raw['revision_id'], 'revision id'),
        digest,
    )


def decode_pair_piece(payload):
    data = load_json(payload)
    if not isinstance(data, dict) or data.keys() != {'parents', 'body', 'sha256'}:
        raise ValueError('invalid pair piece envelope')
    parents = data['parents']
    if not isinstance(parents, list) or len(parents) != 2:
        raise ValueError('a pair piece requires exactly two parents')
    if data['sha256'] != sha256_text(canonical_json({'parents': parents, 'body': data['body']})):
        raise ValueError('pair piece digest mismatch')
    total_mass, units = decode_joint_body(data['body'])
    decoded_parents = tuple(_decode_parent(parent) for parent in parents)
    return DecodedPairPiece(decoded_parents, canonical_json(data['body']), total_mass, units,
                            canonical_json(data))


def derive_edition_body(units, edition):
    """Replay one edition's anonymous mass units from the joint evidence."""
    projected = []
    for unit in units:
        points = unit.old if edition == 'old' else unit.new
        projected.append(project_mass(points, unit.mass))
    return encode_mass_body(tuple(projected))
