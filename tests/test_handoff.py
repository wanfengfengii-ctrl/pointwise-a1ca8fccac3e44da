import json
import sqlite3
from fractions import Fraction as F

from center.accept import accept
from center.handoff_export import export_report
from center.publish import initialize_center, publish
from center.report_lookup import read
from station.batch_store import BatchStore
from station.intake import import_batch
from station.issue import initialize_station, issue
from station.revisions import revise
from tests import ArchiveCase, IDENTITY, piece, single_issue


class HandoffTests(ArchiveCase):
    def test_fraction_roundtrip_reopen_initialization_and_unknown_report(self):
        with self.station() as station, self.center() as center:
            batch = import_batch(station, [piece(mass='2/3')])
            first_revision = revise(station, batch, {'panel': IDENTITY})
            first_payload = issue(station, batch, first_revision)
            first_receipt = accept(center, first_payload)
        with self.center() as center:
            first_report = publish(center, first_receipt, 1, 1)

        with self.station() as station, self.center() as center:
            shifted = [[1, 0, 2], [0, 1, 0]]
            second_revision = revise(station, batch, {'panel': shifted})
            second_payload = issue(station, batch, second_revision)
            second_receipt = accept(center, second_payload)
        with self.center() as center:
            second_report = publish(center, second_receipt, 1, 1)

        with self.station() as station:
            initialize_station(station)
            self.assertEqual(BatchStore(station).load(batch).pieces[0].mass, F(2, 3))
            self.assertEqual(issue(station, batch, first_revision), first_payload)
            self.assertEqual(issue(station, batch, second_revision), second_payload)
            self.assertEqual(station.execute('SELECT count(*) FROM revisions').fetchone()[0], 2)
        with self.center() as center:
            initialize_center(center)
            self.assertNotEqual(first_receipt, second_receipt)
            self.assertNotEqual(first_report, second_report)
            self.assertEqual(accept(center, first_payload), first_receipt)
            self.assertEqual(accept(center, second_payload), second_receipt)
            cases = [
                (first_report, first_receipt, first_revision, first_payload, (F(1, 3), F(1, 6), F(1, 6), F(0))),
                (second_report, second_receipt, second_revision, second_payload, (F(0), F(1, 2), F(0), F(1, 6))),
            ]
            for report_id, receipt_id, revision_id, payload, expected in cases:
                with self.subTest(report_id=report_id):
                    snapshot = read(center, report_id)
                    self.assertEqual(snapshot.partition.masses, expected)
                    self.assertEqual((snapshot.partition.cuts.x, snapshot.partition.cuts.y), (1, 1))
                    self.assertEqual(snapshot.receipt_id, receipt_id)
                    self.assertEqual(snapshot.provenance.revision_id, revision_id)
                    self.assertEqual(snapshot.provenance.body_sha256, json.loads(payload)['body_sha256'])
                    exported = json.loads(export_report(center, report_id))
                    self.assertEqual(exported['cuts'], {'x': '1', 'y': '1'})
                    self.assertEqual(exported['receipt_id'], receipt_id)
                    self.assertEqual(exported['report_id'], report_id)
                    self.assertEqual(exported['provenance']['revision_id'], revision_id)
                    self.assertEqual(exported['zones'], [
                        {'zone': zone, 'mass': str(mass)}
                        for zone, mass in zip(('LL', 'HL', 'LH', 'HH'), expected)
                    ])
            self.assertEqual(center.execute('SELECT count(*) FROM receipts').fetchone()[0], 2)
            self.assertEqual(center.execute('SELECT count(*) FROM reports').fetchone()[0], 2)
            self.assertIsNone(read(center, 999))
            self.assertIsNone(export_report(center, 999))

    def test_fractional_retry(self):
        with self.station() as station, self.center() as center:
            receipt = accept(center, single_issue(station, mass='2/3'))
        with self.center() as center:
            center.execute('''
                CREATE TRIGGER fail_signing BEFORE INSERT ON report_signatures
                BEGIN
                    SELECT RAISE(ABORT, 'signing failure');
                END
            ''')
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'signing failure'):
                publish(center, receipt, 1, 1)
        with self.center() as center:
            self.assertEqual(center.execute('SELECT count(*) FROM reports').fetchone()[0], 0)
            self.assertEqual(center.execute('SELECT count(*) FROM report_signatures').fetchone()[0], 0)
            self.assertEqual(center.execute('SELECT count(*) FROM receipts').fetchone()[0], 1)
            self.assertIsNone(read(center, 1))
            center.execute('DROP TRIGGER fail_signing')
            report_id = publish(center, receipt, 1, 1)
        with self.center() as center:
            snapshot = read(center, report_id)
            self.assertEqual(snapshot.partition.masses, (F(1, 3), F(1, 6), F(1, 6), 0))
            self.assertEqual(snapshot.receipt_id, receipt)
            self.assertEqual(center.execute('SELECT count(*) FROM reports').fetchone()[0], 1)
            self.assertEqual(center.execute('SELECT count(*) FROM report_signatures').fetchone()[0], 1)
