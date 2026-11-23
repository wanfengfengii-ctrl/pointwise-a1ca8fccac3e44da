from dataclasses import dataclass

from archive import write_transaction
from exact import require_id, sha256_text


@dataclass(frozen=True)
class StoredPairReceipt:
    id: int
    old_receipt_id: int
    new_receipt_id: int
    body_sha256: str
    body: str
    payload: str


class PairReceiptStore:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS pair_receipts (
                id INTEGER PRIMARY KEY,
                station_id TEXT NOT NULL,
                old_issue_id INTEGER NOT NULL,
                new_issue_id INTEGER NOT NULL,
                old_receipt_id INTEGER NOT NULL REFERENCES receipts(id),
                new_receipt_id INTEGER NOT NULL REFERENCES receipts(id),
                batch_id INTEGER NOT NULL,
                old_revision_id INTEGER NOT NULL,
                new_revision_id INTEGER NOT NULL,
                body_sha256 TEXT NOT NULL,
                body TEXT NOT NULL,
                payload TEXT NOT NULL,
                UNIQUE (station_id, old_issue_id, new_issue_id)
            )
        ''')

    def record(self, piece, old_receipt_id, new_receipt_id):
        old, new = piece.parents
        binding = (old.station_id, old.issue_id, new.issue_id)
        with write_transaction(self.connection):
            row = self.connection.execute('''
                SELECT id, payload FROM pair_receipts
                WHERE station_id = ? AND old_issue_id = ? AND new_issue_id = ?
            ''', binding).fetchone()
            if row is not None:
                if row[1] != piece.payload:
                    raise ValueError('conflicting content for an accepted pair binding')
                return row[0]
            cursor = self.connection.execute('''
                INSERT INTO pair_receipts (
                    station_id, old_issue_id, new_issue_id, old_receipt_id, new_receipt_id,
                    batch_id, old_revision_id, new_revision_id, body_sha256, body, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (*binding, old_receipt_id, new_receipt_id, old.batch_id, old.revision_id,
                  new.revision_id, sha256_text(piece.body), piece.body, piece.payload))
        return cursor.lastrowid

    def get(self, pair_receipt_id):
        require_id(pair_receipt_id, 'pair receipt id')
        row = self.connection.execute('''
            SELECT id, old_receipt_id, new_receipt_id, body_sha256, body, payload
            FROM pair_receipts WHERE id = ?
        ''', (pair_receipt_id,)).fetchone()
        return None if row is None else StoredPairReceipt(*row)
