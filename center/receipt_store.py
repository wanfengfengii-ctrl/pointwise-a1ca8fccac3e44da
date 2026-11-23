from dataclasses import dataclass

from archive import write_transaction
from center.provenance import IssueProvenance, same_issue_content
from exact import require_id


@dataclass(frozen=True)
class StoredReceipt:
    id: int
    provenance: IssueProvenance
    body: str


class ReceiptStore:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY,
                station_id TEXT NOT NULL,
                issue_id INTEGER NOT NULL,
                batch_id INTEGER NOT NULL,
                revision_id INTEGER NOT NULL,
                body_sha256 TEXT NOT NULL,
                body TEXT NOT NULL,
                UNIQUE (station_id, issue_id)
            )
        ''')

    @staticmethod
    def _from_row(row):
        receipt_id, station_id, issue_id, batch_id, revision_id, digest, body = row
        provenance = IssueProvenance(station_id, issue_id, batch_id, revision_id, digest)
        return StoredReceipt(receipt_id, provenance, body)

    def record(self, provenance, body):
        with write_transaction(self.connection):
            row = self.connection.execute('''
                SELECT id, station_id, issue_id, batch_id, revision_id, body_sha256, body
                FROM receipts WHERE station_id = ? AND issue_id = ?
            ''', provenance.identity).fetchone()
            if row is not None:
                existing = self._from_row(row)
                if not same_issue_content(existing.provenance, existing.body, provenance, body):
                    raise ValueError('conflicting content for an accepted issue identity')
                return existing.id
            cursor = self.connection.execute('''
                INSERT INTO receipts (station_id, issue_id, batch_id, revision_id, body_sha256, body)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (*provenance.identity, provenance.batch_id, provenance.revision_id, provenance.body_sha256, body))
        return cursor.lastrowid

    def get(self, receipt_id):
        require_id(receipt_id, 'receipt id')
        row = self.connection.execute('''
            SELECT id, station_id, issue_id, batch_id, revision_id, body_sha256, body
            FROM receipts WHERE id = ?
        ''', (receipt_id,)).fetchone()
        return None if row is None else self._from_row(row)
