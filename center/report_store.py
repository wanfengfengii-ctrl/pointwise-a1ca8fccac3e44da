from archive import write_transaction
from center.report_snapshot import decode_snapshot, encode_snapshot
from exact import require_id, sha256_text


class ReportStore:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY,
                receipt_id INTEGER NOT NULL REFERENCES receipts(id),
                snapshot TEXT NOT NULL
            )
        ''')
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS report_signatures (
                report_id INTEGER PRIMARY KEY REFERENCES reports(id),
                snapshot_sha256 TEXT NOT NULL
            )
        ''')

    def save(self, snapshot):
        payload = encode_snapshot(snapshot)
        with write_transaction(self.connection):
            report_id = self.connection.execute(
                'INSERT INTO reports (receipt_id, snapshot) VALUES (?, ?)', (snapshot.receipt_id, payload)
            ).lastrowid
            self.connection.execute(
                'INSERT INTO report_signatures (report_id, snapshot_sha256) VALUES (?, ?)',
                (report_id, sha256_text(payload)),
            )
        return report_id

    def load(self, report_id):
        require_id(report_id, 'report id')
        row = self.connection.execute('''
            SELECT reports.receipt_id, reports.snapshot, report_signatures.snapshot_sha256
            FROM reports JOIN report_signatures ON report_signatures.report_id = reports.id
            WHERE reports.id = ?
        ''', (report_id,)).fetchone()
        if row is None:
            return None
        receipt_id, payload, digest = row
        if sha256_text(payload) != digest:
            raise ValueError('stored report digest mismatch')
        snapshot = decode_snapshot(payload)
        if snapshot.receipt_id != receipt_id:
            raise ValueError('stored report receipt mismatch')
        return snapshot
