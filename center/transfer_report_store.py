from archive import write_transaction
from center.transfer_snapshot import decode_transfer_snapshot
from exact import require_id, sha256_text


class TransferReportStore:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS transfer_reports (
                id INTEGER PRIMARY KEY,
                pair_receipt_id INTEGER NOT NULL REFERENCES pair_receipts(id),
                snapshot TEXT NOT NULL
            )
        ''')
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS transfer_report_signatures (
                report_id INTEGER PRIMARY KEY REFERENCES transfer_reports(id),
                snapshot_sha256 TEXT NOT NULL
            )
        ''')

    def save(self, pair_receipt_id, snapshot):
        with write_transaction(self.connection):
            report_id = self.connection.execute(
                'INSERT INTO transfer_reports (pair_receipt_id, snapshot) VALUES (?, ?)',
                (pair_receipt_id, snapshot),
            ).lastrowid
            self.connection.execute(
                'INSERT INTO transfer_report_signatures (report_id, snapshot_sha256) VALUES (?, ?)',
                (report_id, sha256_text(snapshot)),
            )
        return report_id

    def load(self, report_id):
        require_id(report_id, 'report id')
        row = self.connection.execute('''
            SELECT transfer_reports.pair_receipt_id, transfer_reports.snapshot,
                   transfer_report_signatures.snapshot_sha256
            FROM transfer_reports
            JOIN transfer_report_signatures ON transfer_report_signatures.report_id = transfer_reports.id
            WHERE transfer_reports.id = ?
        ''', (report_id,)).fetchone()
        if row is None:
            return None
        pair_receipt_id, payload, digest = row
        if sha256_text(payload) != digest:
            raise ValueError('stored transfer report digest mismatch')
        decoded = decode_transfer_snapshot(payload)
        if decoded['pair_receipt_id'] != pair_receipt_id:
            raise ValueError('stored transfer report pair receipt mismatch')
        return decoded
