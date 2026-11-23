from collections.abc import Mapping

from station.batch_store import BatchStore, WeighedTriangle
from station.mesh import validate_triangle
from station.weighing import positive_mass


def import_batch(connection, pieces):
    try:
        records = iter(pieces)
    except TypeError as error:
        raise ValueError('batch requires an iterable of piece records') from error
    validated = []
    names = set()
    for record in records:
        if not isinstance(record, Mapping) or set(record) != {'name', 'vertices', 'mass'}:
            raise ValueError('each piece requires name, vertices and mass')
        name = record['name']
        if not isinstance(name, str) or not name.strip() or '\x00' in name:
            raise ValueError('piece name must be nonempty text without NUL')
        if name in names:
            raise ValueError(f'duplicate piece name {name!r}')
        names.add(name)
        validated.append(WeighedTriangle(name, validate_triangle(record['vertices']), positive_mass(record['mass'])))
    if not validated:
        raise ValueError('batch requires at least one piece')
    return BatchStore(connection).save(validated)
