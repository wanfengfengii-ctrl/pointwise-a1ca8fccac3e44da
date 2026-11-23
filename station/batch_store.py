from dataclasses import dataclass
from fractions import Fraction

from archive import write_transaction
from exact import canonical_json, load_json, require_id
from station.mesh import SourceTriangle, validate_triangle
from station.weighing import positive_mass


@dataclass(frozen=True)
class WeighedTriangle:
    name: str
    triangle: SourceTriangle
    mass: Fraction


@dataclass(frozen=True)
class Batch:
    id: int
    pieces: tuple[WeighedTriangle, ...]


class BatchStore:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('CREATE TABLE IF NOT EXISTS batches (id INTEGER PRIMARY KEY)')
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS source_pieces (
                batch_id INTEGER NOT NULL REFERENCES batches(id),
                name TEXT NOT NULL,
                vertices TEXT NOT NULL,
                mass TEXT NOT NULL,
                PRIMARY KEY (batch_id, name)
            )
        ''')

    def save(self, pieces):
        rows = [
            (piece.name, canonical_json([[str(x), str(y)] for x, y in piece.triangle.vertices]),
             str(piece.mass))
            for piece in pieces
        ]
        with write_transaction(self.connection):
            batch_id = self.connection.execute('INSERT INTO batches DEFAULT VALUES').lastrowid
            self.connection.executemany(
                'INSERT INTO source_pieces (batch_id, name, vertices, mass) VALUES (?, ?, ?, ?)',
                ((batch_id, name, vertices, mass) for name, vertices, mass in rows),
            )
        return batch_id

    def load(self, batch_id):
        require_id(batch_id, 'batch id')
        batch_row = self.connection.execute('SELECT id FROM batches WHERE id = ?', (batch_id,)).fetchone()
        if batch_row is None:
            raise KeyError(f'batch {batch_id} not found')
        rows = self.connection.execute(
            'SELECT name, vertices, mass FROM source_pieces WHERE batch_id = ? ORDER BY name',
            (batch_id,),
        )
        return Batch(batch_id, tuple(
            WeighedTriangle(name, validate_triangle(load_json(vertices)), positive_mass(mass))
            for name, vertices, mass in rows
        ))
