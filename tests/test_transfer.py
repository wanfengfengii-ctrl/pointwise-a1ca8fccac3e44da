import json
import sqlite3
from fractions import Fraction as F

from center.accept import accept, accept_pair
from center.handoff_export import export_report, export_transfer
from center.publish import publish, publish_transfer
from center.report_lookup import read, read_transfer
from exact import canonical_json, sha256_text
from station.intake import import_batch
from station.issue import issue, issue_pair
from station.revisions import revise
from tests import ArchiveCase, IDENTITY, piece

FOLD_X = [[1, 0, 0], [0, 0, 0]]  # image (x, 0)
FOLD_Y = [[0, 1, 0], [0, 0, 0]]  # image (y, 0)
MARGINAL = (F(3, 4), F(1, 4), F(0), F(0))


class TransferCase(ArchiveCase):
    def _scene(self, station, center, pieces, calibrations):
        batch = import_batch(station, pieces)
        revisions = [revise(station, batch, calibration) for calibration in calibrations]
        payloads = [issue(station, batch, revision) for revision in revisions]
        receipts = [accept(center, payload) for payload in payloads]
        return batch, revisions, payloads, receipts

    def _incident(self, station, center):
        # One unit-mass triangle; old and aligned editions fold onto (x, 0),
        # the crossed edition folds onto (y, 0).  All three V1 bodies match.
        calibrations = [{'panel': FOLD_X}, {'panel': FOLD_X}, {'panel': FOLD_Y}]
        return self._scene(station, center, [piece()], calibrations)


class TransferTests(TransferCase):
    def test_aligned_and_crossed_transfer(self):
        with self.station() as station, self.center() as center:
            batch, revisions, payloads, receipts = self._incident(station, center)
            old_rev, aligned_rev, crossed_rev = revisions
            old_receipt, aligned_receipt, crossed_receipt = receipts
            aligned_pair = issue_pair(station, batch, old_rev, aligned_rev)
            crossed_pair = issue_pair(station, batch, old_rev, crossed_rev)
            self.assertNotEqual(aligned_pair, crossed_pair)
            aligned_pair_receipt = accept_pair(center, aligned_pair, old_receipt, aligned_receipt)
            crossed_pair_receipt = accept_pair(center, crossed_pair, old_receipt, crossed_receipt)
            self.assertNotEqual(aligned_pair_receipt, crossed_pair_receipt)
        # The station archive is closed; the center signs from accepted evidence.
        with self.center() as center:
            aligned_report = publish_transfer(center, aligned_pair_receipt, 1, 1, 1, 1)
            crossed_report = publish_transfer(center, crossed_pair_receipt, 1, 1, 1, 1)
            single_reports = [publish(center, receipt, 1, 1) for receipt in receipts]
        with self.center() as center:
            zones = [read(center, report_id).partition.masses for report_id in single_reports]
            self.assertEqual(zones, [MARGINAL] * 3, 'TRANSFER_SINGLE_EDITION_MARGINAL_MISMATCH')
            aligned = read_transfer(center, aligned_report)
            crossed = read_transfer(center, crossed_report)
            expected_aligned = [[F(3, 4), 0, 0, 0], [0, F(1, 4), 0, 0],
                                [0, 0, 0, 0], [0, 0, 0, 0]]
            expected_crossed = [[F(1, 2), F(1, 4), 0, 0], [F(1, 4), 0, 0, 0],
                                [0, 0, 0, 0], [0, 0, 0, 0]]
            self.assertEqual(aligned['matrix'], expected_aligned)
            self.assertEqual(crossed['matrix'], expected_crossed)
            for report in (aligned, crossed):
                self.assertEqual([sum(row) for row in report['matrix']], list(MARGINAL))
                self.assertEqual([sum(column) for column in zip(*report['matrix'])], list(MARGINAL))
                self.assertEqual(report['cuts'], [{'x': F(1), 'y': F(1)}] * 2)
            self.assertEqual(aligned['report_id'], aligned_report)
            self.assertEqual(aligned['pair_receipt_id'], aligned_pair_receipt)
            self.assertEqual([parent['receipt_id'] for parent in aligned['parents']],
                             [old_receipt, aligned_receipt])
            self.assertEqual(aligned['parents'][0]['provenance']['revision_id'], old_rev)
            self.assertEqual(aligned['parents'][1]['provenance']['revision_id'], aligned_rev)
            self.assertEqual([parent['receipt_id'] for parent in crossed['parents']],
                             [old_receipt, crossed_receipt])
            exported = json.loads(export_transfer(center, crossed_report))
            self.assertEqual(exported['report_id'], crossed_report)
            self.assertEqual(exported['pair_receipt_id'], crossed_pair_receipt)
            self.assertEqual(exported['cuts'], [{'x': '1', 'y': '1'}] * 2)
            self.assertEqual(exported['matrix'], [['1/2', '1/4', '0', '0'], ['1/4', '0', '0', '0'],
                                                  ['0', '0', '0', '0'], ['0', '0', '0', '0']])
            self.assertEqual([parent['receipt_id'] for parent in exported['parents']],
                             [old_receipt, crossed_receipt])
            self.assertIsNone(read_transfer(center, 999))
            self.assertIsNone(export_transfer(center, 999))
            print('POINTWISE_SCENARIO ' + json.dumps({
                'case_id': 'v10.transfer_matrix',
                'input': {'triangle': [[0, 0], [2, 0], [0, 2]], 'mass': '1',
                          'old_calibration': FOLD_X, 'new_calibration': FOLD_Y,
                          'old_cuts': [1, 1], 'new_cuts': [1, 1]},
                'expected': [[str(mass) for mass in row] for row in expected_crossed],
                'actual': [[str(mass) for mass in row] for row in crossed['matrix']],
                'marginals': [str(mass) for mass in MARGINAL],
                'code_paths': ['station/issue.py', 'station/issue_payload.py', 'center/accept.py',
                               'center/pair_payload.py', 'center/transfer_matrix.py',
                               'center/publish.py', 'center/report_lookup.py',
                               'center/handoff_export.py'],
                'oracle': 'Both editions share the single-edition account (3/4, 1/4, 0, 0), yet the '
                          'source quarter with x >= 1, y < 1 moves HL->LL and the quarter with '
                          'x < 1, y >= 1 moves LL->HL under the crossed fold.',
            }, sort_keys=True))

    def test_pair_piece_format_and_reissue_after_reopen(self):
        with self.station() as station, self.center() as center:
            batch, revisions, payloads, receipts = self._incident(station, center)
            pair = issue_pair(station, batch, revisions[0], revisions[2])
            data = json.loads(pair)
            self.assertEqual(set(data), {'parents', 'body', 'sha256'})
            envelopes = [json.loads(payload) for payload in payloads]
            expected_parents = [
                {field: envelopes[index][field] for field in
                 ('station_id', 'issue_id', 'batch_id', 'revision_id', 'body_sha256')}
                for index in (0, 2)
            ]
            self.assertEqual(data['parents'], expected_parents)
            self.assertEqual(data['sha256'], sha256_text(
                canonical_json({'parents': data['parents'], 'body': data['body']})))
            self.assertNotIn('panel', pair, 'pair piece must not leak piece names')
            units = data['body']['units']
            self.assertEqual(len(units), 1)
            self.assertEqual(set(units[0]), {'mass', 'old', 'new'})
            self.assertEqual(units[0]['mass'], '1')
            self.assertEqual(data['body']['total_mass'], '1')
        with self.station() as station:
            self.assertEqual(issue_pair(station, batch, revisions[0], revisions[2]), pair)
            self.assertEqual(station.execute('SELECT count(*) FROM pair_issues').fetchone()[0], 1)

    def test_line_and_point_duplicate_units(self):
        pieces = [piece('first', '1/2'), piece('second', '1/2')]
        to_point = {'first': [[0, 0, 1], [0, 0, 1]], 'second': [[0, 0, 1], [0, 0, 1]]}
        to_line = {'first': [[0, 0, 1], [1, 0, 0]], 'second': [[0, 0, 1], [1, 0, 0]]}
        with self.station() as station, self.center() as center:
            batch, revisions, payloads, receipts = self._scene(
                station, center, pieces, [to_point, to_line])
            pair = issue_pair(station, batch, revisions[0], revisions[1])
            units = json.loads(pair)['body']['units']
            self.assertEqual([unit['mass'] for unit in units], ['1/2', '1/2'],
                             'duplicate anonymous units must keep their own masses')
            pair_receipt = accept_pair(center, pair, receipts[0], receipts[1])
        with self.center() as center:
            transfer_report = publish_transfer(center, pair_receipt, 1, 1, 1, '3/2')
            old_single = publish(center, receipts[0], 1, 1)
            new_single = publish(center, receipts[1], 1, '3/2')
        with self.center() as center:
            report = read_transfer(center, transfer_report)
            expected = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0],
                        [0, F(15, 16), 0, F(1, 16)]]
            self.assertEqual(report['matrix'], expected)
            self.assertEqual([sum(row) for row in report['matrix']],
                             list(read(center, old_single).partition.masses))
            self.assertEqual([sum(column) for column in zip(*report['matrix'])],
                             list(read(center, new_single).partition.masses))
            exported = json.loads(export_transfer(center, transfer_report))
            self.assertEqual(exported['matrix'][3], ['0', '15/16', '0', '1/16'])
            self.assertEqual(exported['cuts'], [{'x': '1', 'y': '1'}, {'x': '1', 'y': '3/2'}])

    def test_parent_mismatch_and_reversed_order(self):
        with self.station() as station, self.center() as center:
            batch, revisions, payloads, receipts = self._incident(station, center)
            old_rev, aligned_rev, crossed_rev = revisions
            old_receipt, aligned_receipt, crossed_receipt = receipts
            pair = issue_pair(station, batch, old_rev, aligned_rev)
            # The crossed receipt carries an identical body but is the wrong parent.
            with self.assertRaises(ValueError):
                accept_pair(center, pair, crossed_receipt, aligned_receipt)
            with self.assertRaises(ValueError):
                accept_pair(center, pair, aligned_receipt, old_receipt)
            with self.assertRaises(KeyError):
                accept_pair(center, pair, old_receipt, 999)
            with self.assertRaises(KeyError):
                accept_pair(center, pair, 999, aligned_receipt)
            self.assertEqual(center.execute('SELECT count(*) FROM pair_receipts').fetchone()[0], 0)
            pair_receipt = accept_pair(center, pair, old_receipt, aligned_receipt)
            # The reversed ordered pair is a different issuance and binding.
            reversed_pair = issue_pair(station, batch, aligned_rev, old_rev)
            self.assertNotEqual(reversed_pair, pair)
            reversed_receipt = accept_pair(center, reversed_pair, aligned_receipt, old_receipt)
            self.assertNotEqual(reversed_receipt, pair_receipt)
        with self.center() as center:
            report_id = publish_transfer(center, reversed_receipt, 1, 1, 1, 1)
            report = read_transfer(center, report_id)
            self.assertEqual([parent['receipt_id'] for parent in report['parents']],
                             [aligned_receipt, old_receipt])
            self.assertEqual(report['matrix'], [[F(3, 4), 0, 0, 0], [0, F(1, 4), 0, 0],
                                                [0, 0, 0, 0], [0, 0, 0, 0]])

    def test_evidence_tampering_rejected(self):
        with self.station() as station, self.center() as center:
            batch, revisions, payloads, receipts = self._incident(station, center)
            pair = issue_pair(station, batch, revisions[0], revisions[2])
            moved = json.loads(pair)
            point = moved['body']['units'][0]['old'][0]
            point[0] = str(F(point[0]) + 1)
            moved['sha256'] = sha256_text(
                canonical_json({'parents': moved['parents'], 'body': moved['body']}))
            with self.assertRaisesRegex(ValueError, 'reproduce'):
                accept_pair(center, json.dumps(moved), receipts[0], receipts[2])
            stale = json.loads(pair)
            stale['body']['units'][0]['mass'] = '2'
            stale['body']['total_mass'] = '2'
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                accept_pair(center, json.dumps(stale), receipts[0], receipts[2])
            for bad in ('not json', '{}', json.dumps({'parents': [], 'body': {}, 'sha256': ''})):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    accept_pair(center, bad, receipts[0], receipts[2])
            self.assertEqual(center.execute('SELECT count(*) FROM pair_receipts').fetchone()[0], 0)
            self.assertEqual(accept_pair(center, pair, receipts[0], receipts[2]), 1)

    def test_same_edition_pair_rejected(self):
        with self.station() as station, self.center() as center:
            batch, revisions, payloads, receipts = self._incident(station, center)
            with self.assertRaises(ValueError):
                issue_pair(station, batch, revisions[0], revisions[0])
            legit = json.loads(issue_pair(station, batch, revisions[0], revisions[2]))
            crafted = {'parents': [legit['parents'][0], legit['parents'][0]],
                       'body': legit['body']}
            crafted['sha256'] = sha256_text(
                canonical_json({'parents': crafted['parents'], 'body': crafted['body']}))
            with self.assertRaisesRegex(ValueError, 'different revisions'):
                accept_pair(center, json.dumps(crafted), receipts[0], receipts[0])
            self.assertEqual(center.execute('SELECT count(*) FROM pair_receipts').fetchone()[0], 0)

    def test_redelivery_and_binding_conflict(self):
        pieces = [piece('first', 1), piece('second', 2)]
        moved = [[1, 0, 3], [0, 1, 0]]
        calibrations = [
            {'first': IDENTITY, 'second': IDENTITY},
            {'first': moved, 'second': moved},
        ]
        with self.station() as station, self.center() as center:
            batch, revisions, payloads, receipts = self._scene(
                station, center, pieces, calibrations)
            pair = issue_pair(station, batch, revisions[0], revisions[1])
            pair_receipt = accept_pair(center, pair, receipts[0], receipts[1])
            reformatted = json.dumps(json.loads(pair), indent=2)
            self.assertEqual(accept_pair(center, reformatted, receipts[0], receipts[1]), pair_receipt)
            crafted = json.loads(pair)
            crafted['body']['units'] = list(reversed(crafted['body']['units']))
            crafted['sha256'] = sha256_text(
                canonical_json({'parents': crafted['parents'], 'body': crafted['body']}))
            with self.assertRaisesRegex(ValueError, 'conflicting content'):
                accept_pair(center, json.dumps(crafted), receipts[0], receipts[1])
            self.assertEqual(center.execute('SELECT count(*) FROM pair_receipts').fetchone()[0], 1)
        with self.center() as center:
            self.assertEqual(accept_pair(center, pair, receipts[0], receipts[1]), pair_receipt)
            self.assertEqual(center.execute('SELECT count(*) FROM pair_receipts').fetchone()[0], 1)

    def test_issue_pair_unknown_and_invalid(self):
        with self.station() as station:
            batch = import_batch(station, [piece()])
            first = revise(station, batch, {'panel': IDENTITY})
            second = revise(station, batch, {'panel': FOLD_X})
            issue(station, batch, first)
            with self.assertRaises(KeyError):
                issue_pair(station, 999, first, second)
            with self.assertRaises(KeyError):
                issue_pair(station, batch, first, 999)
            with self.assertRaises(KeyError):
                issue_pair(station, batch, first, second)
            self.assertEqual(station.execute('SELECT count(*) FROM pair_issues').fetchone()[0], 0)
            issue(station, batch, second)
            pair = issue_pair(station, batch, first, second)
            self.assertEqual(issue_pair(station, batch, first, second), pair)
            for bad in ('1', 0, -1, 1.5, True):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    issue_pair(station, bad, first, second)

    def test_publish_transfer_unknown_and_invalid(self):
        with self.station() as station, self.center() as center:
            batch, revisions, payloads, receipts = self._incident(station, center)
            pair = issue_pair(station, batch, revisions[0], revisions[2])
            pair_receipt = accept_pair(center, pair, receipts[0], receipts[2])
        with self.center() as center:
            for bad_cut in ('not a rational', '1/0', None, 1.0, True):
                with self.subTest(cut=bad_cut), self.assertRaises(ValueError):
                    publish_transfer(center, pair_receipt, bad_cut, 1, 1, 1)
            with self.assertRaises(KeyError):
                publish_transfer(center, 999, 1, 1, 1, 1)
            with self.assertRaises(ValueError):
                publish_transfer(center, '1', 1, 1, 1, 1)
            self.assertEqual(center.execute('SELECT count(*) FROM transfer_reports').fetchone()[0], 0)
            self.assertEqual(
                center.execute('SELECT count(*) FROM transfer_report_signatures').fetchone()[0], 0)

    def test_transfer_write_failure_and_retry(self):
        with self.station() as station, self.center() as center:
            batch, revisions, payloads, receipts = self._incident(station, center)
            pair = issue_pair(station, batch, revisions[0], revisions[2])
            pair_receipt = accept_pair(center, pair, receipts[0], receipts[2])
        with self.center() as center:
            center.execute('''
                CREATE TRIGGER fail_transfer_signing BEFORE INSERT ON transfer_report_signatures
                BEGIN
                    SELECT RAISE(ABORT, 'signing failure');
                END
            ''')
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'signing failure'):
                publish_transfer(center, pair_receipt, 1, 1, 1, 1)
        with self.center() as center:
            self.assertEqual(center.execute('SELECT count(*) FROM transfer_reports').fetchone()[0], 0)
            self.assertEqual(
                center.execute('SELECT count(*) FROM transfer_report_signatures').fetchone()[0], 0)
            self.assertEqual(center.execute('SELECT count(*) FROM pair_receipts').fetchone()[0], 1)
            self.assertIsNone(read_transfer(center, 1))
            center.execute('DROP TRIGGER fail_transfer_signing')
            report_id = publish_transfer(center, pair_receipt, 1, 1, 1, 1)
        with self.center() as center:
            report = read_transfer(center, report_id)
            self.assertEqual(report['matrix'][0][0], F(1, 2))
            self.assertEqual(center.execute('SELECT count(*) FROM transfer_reports').fetchone()[0], 1)

    def test_pair_accept_write_failure_and_retry(self):
        with self.station() as station, self.center() as center:
            batch, revisions, payloads, receipts = self._incident(station, center)
            pair = issue_pair(station, batch, revisions[0], revisions[2])
            center.execute('''
                CREATE TRIGGER fail_pair_receipt BEFORE INSERT ON pair_receipts
                BEGIN
                    SELECT RAISE(ABORT, 'pair receipt failure');
                END
            ''')
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'pair receipt failure'):
                accept_pair(center, pair, receipts[0], receipts[2])
            self.assertEqual(center.execute('SELECT count(*) FROM pair_receipts').fetchone()[0], 0)
            center.execute('DROP TRIGGER fail_pair_receipt')
            self.assertEqual(accept_pair(center, pair, receipts[0], receipts[2]), 1)
            self.assertEqual(center.execute('SELECT count(*) FROM pair_receipts').fetchone()[0], 1)

    def test_offline_reopen_and_station_errata(self):
        with self.station() as station, self.center() as center:
            batch, revisions, payloads, receipts = self._incident(station, center)
            pair = issue_pair(station, batch, revisions[0], revisions[2])
            pair_receipt = accept_pair(center, pair, receipts[0], receipts[2])
        with self.center() as center:
            report_id = publish_transfer(center, pair_receipt, 1, 1, 1, 1)
        # A later errata revision at the station must not disturb the signed report.
        with self.station() as station:
            errata = revise(station, batch, {'panel': IDENTITY})
            issue(station, batch, errata)
        with self.center() as center:
            report = read_transfer(center, report_id)
            self.assertEqual(report['report_id'], report_id)
            self.assertEqual(report['pair_receipt_id'], pair_receipt)
            self.assertEqual(report['matrix'][0], [F(1, 2), F(1, 4), 0, 0])
            self.assertEqual(report['cuts'], [{'x': F(1), 'y': F(1)}] * 2)
            self.assertEqual([parent['receipt_id'] for parent in report['parents']],
                             [receipts[0], receipts[2]])
            exported = export_transfer(center, report_id)
            self.assertEqual(exported, export_transfer(center, report_id))
            self.assertEqual(json.loads(exported)['parents'][0]['provenance']['body_sha256'],
                             json.loads(payloads[0])['body_sha256'])

    def test_independent_cut_pairs(self):
        with self.station() as station, self.center() as center:
            batch, revisions, payloads, receipts = self._incident(station, center)
            pair = issue_pair(station, batch, revisions[0], revisions[2])
            pair_receipt = accept_pair(center, pair, receipts[0], receipts[2])
        with self.center() as center:
            report_id = publish_transfer(center, pair_receipt, 1, 1, '1/2', '3/2')
            old_single = publish(center, receipts[0], 1, 1)
            new_single = publish(center, receipts[2], '1/2', '3/2')
        with self.center() as center:
            report = read_transfer(center, report_id)
            self.assertEqual(report['cuts'], [{'x': F(1), 'y': F(1)}, {'x': F(1, 2), 'y': F(3, 2)}])
            self.assertEqual([sum(row) for row in report['matrix']],
                             list(read(center, old_single).partition.masses))
            self.assertEqual([sum(column) for column in zip(*report['matrix'])],
                             list(read(center, new_single).partition.masses))
            self.assertEqual(report['matrix'], [[F(1, 4), F(1, 2), 0, 0],
                                                [F(3, 16), F(1, 16), 0, 0],
                                                [0, 0, 0, 0], [0, 0, 0, 0]])
