from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from archive import write_transaction
from exact import canonical_json, load_json, require_id
from station.batch_store import BatchStore
from station.calibration import AffineCalibration, validate_calibration


@dataclass(frozen=True)
class Revision:
    id: int
    batch_id: int
    calibrations: Mapping[str, AffineCalibration]


class RevisionStore:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS revisions (
                id INTEGER PRIMARY KEY,
                batch_id INTEGER NOT NULL REFERENCES batches(id),
                calibrations TEXT NOT NULL,
                UNIQUE (batch_id, id)
            )
        ''')

    def append(self, batch_id, calibrations):
        body = canonical_json({
            name: [[str(coefficient) for coefficient in row] for row in (mapping.x, mapping.y)]
            for name, mapping in calibrations.items()
        })
        with write_transaction(self.connection):
            cursor = self.connection.execute(
                'INSERT INTO revisions (batch_id, calibrations) VALUES (?, ?)', (batch_id, body)
            )
        return cursor.lastrowid

    def get(self, batch_id, revision_id):
        require_id(batch_id, 'batch id')
        require_id(revision_id, 'revision id')
        row = self.connection.execute(
            'SELECT calibrations FROM revisions WHERE batch_id = ? AND id = ?', (batch_id, revision_id)
        ).fetchone()
        if row is None:
            raise KeyError(f'revision {revision_id} not found for batch {batch_id}')
        raw = load_json(row[0])
        calibrations = validate_calibration(raw, raw.keys())
        return Revision(revision_id, batch_id, MappingProxyType(calibrations))


def revise(connection, batch_id, calibrations):
    batch = BatchStore(connection).load(batch_id)
    validated = validate_calibration(calibrations, (piece.name for piece in batch.pieces))
    return RevisionStore(connection).append(batch.id, validated)
