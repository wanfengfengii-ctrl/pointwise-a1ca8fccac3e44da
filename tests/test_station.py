import json

from station.batch_store import BatchStore
from station.intake import import_batch
from station.issue import issue
from station.revisions import revise
from tests import ArchiveCase, FOLD_LEFT, FOLD_RIGHT, IDENTITY, POINT_ON_CUTS, piece


class StationTests(ArchiveCase):
    def test_complete_calibration(self):
        with self.station() as station:
            batch = import_batch(station, [piece('first'), piece('second', 2)])
            with self.assertRaises(ValueError):
                revise(station, batch, {'first': IDENTITY})
            with self.assertRaises(KeyError):
                revise(station, 99, {'first': IDENTITY, 'second': IDENTITY})
            self.assertEqual(station.execute('SELECT count(*) FROM revisions').fetchone()[0], 0)
            revision = revise(station, batch, {'first': IDENTITY, 'second': IDENTITY})
            envelope = json.loads(issue(station, batch, revision))
            self.assertEqual(envelope['body']['total_mass'], '3')
            self.assertEqual((envelope['batch_id'], envelope['revision_id']), (batch, revision))

    def test_specified_revision(self):
        with self.station() as station:
            batch = import_batch(station, [piece('first'), piece('second', 2)])
            old_revision = revise(station, batch, {'first': IDENTITY, 'second': POINT_ON_CUTS})
            moved = [[1, 0, 2], [0, 1, 0]]
            new_revision = revise(station, batch, {'first': moved, 'second': POINT_ON_CUTS})
            old_payload = issue(station, batch, old_revision)
            new_payload = issue(station, batch, new_revision)
            self.assertEqual(issue(station, batch, old_revision), old_payload)
            old = json.loads(old_payload)
            new = json.loads(new_payload)
            self.assertEqual(old['revision_id'], old_revision)
            self.assertEqual(new['revision_id'], new_revision)
            self.assertNotEqual(old['issue_id'], new['issue_id'])
            self.assertEqual(old['body']['total_mass'], '3')
            self.assertEqual(new['body']['total_mass'], '3')
            old_area = next(unit for unit in old['body']['units'] if unit['mass'] == '1')
            new_area = next(unit for unit in new['body']['units'] if unit['mass'] == '1')
            self.assertEqual({tuple(p) for p in old_area['vertices']}, {('0', '0'), ('2', '0'), ('0', '2')})
            self.assertEqual({tuple(p) for p in new_area['vertices']}, {('2', '0'), ('4', '0'), ('2', '2')})

    def test_folded_evidence(self):
        with self.station() as station:
            batch = import_batch(station, [piece('private-fold-label'), piece('private-point-label', 2)])
            payloads = []
            for calibration in (FOLD_LEFT, FOLD_RIGHT):
                revision = revise(station, batch, {'private-fold-label': calibration,
                                                   'private-point-label': POINT_ON_CUTS})
                payloads.append(issue(station, batch, revision))
        lines, points = [], []
        for payload in payloads:
            body = json.loads(payload)['body']
            self.assertEqual(body['total_mass'], '3')
            self.assertEqual(len(body['units']), 2)
            self.assertNotIn('private-fold-label', payload)
            self.assertNotIn('private-point-label', payload)
            line = next(unit for unit in body['units'] if unit['mass'] == '1')
            self.assertEqual({tuple(p) for p in line['vertices']}, {('0', '0'), ('2', '0')})
            lines.append(line)
            points.append(next(unit for unit in body['units'] if unit['mass'] == '2'))
        self.assertEqual(points[0], points[1])
        self.assertEqual(points[0]['vertices'], [['1', '1']])
        self.assertNotEqual(lines[0], lines[1], 'FOLDED_ISSUE_EVIDENCE_MISMATCH')

    def test_atomic_reject(self):
        with self.station() as station:
            batch = import_batch(station, [piece('existing')])
            with self.assertRaises(ValueError):
                import_batch(station, [piece('valid-prefix'), piece('negative', -1)])
        with self.station() as station:
            self.assertEqual(station.execute('SELECT count(*) FROM batches').fetchone()[0], 1)
            self.assertEqual(station.execute('SELECT count(*) FROM source_pieces').fetchone()[0], 1)
            saved = BatchStore(station).load(batch)
            self.assertEqual(tuple(p.name for p in saved.pieces), ('existing',))

    def test_invalid_mesh_and_duplicate_piece(self):
        flat = {'name': 'flat', 'vertices': [[0, 0], [1, 1], [2, 2]], 'mass': 1}
        with self.station() as station:
            for records in ([flat], [piece(), piece()], [], [piece(mass=True)]):
                with self.subTest(records=records), self.assertRaises(ValueError):
                    import_batch(station, records)
            self.assertEqual(station.execute('SELECT count(*) FROM batches').fetchone()[0], 0)

    def test_foreign_revision(self):
        with self.station() as station:
            first = import_batch(station, [piece()])
            old_revision = revise(station, first, {'panel': IDENTITY})
            old_payload = issue(station, first, old_revision)
            other = import_batch(station, [piece()])
            foreign = revise(station, other, {'panel': FOLD_LEFT})
            for revision in (foreign, 999):
                with self.subTest(revision=revision), self.assertRaises(KeyError):
                    issue(station, first, revision)
            self.assertEqual(station.execute('SELECT count(*) FROM issues').fetchone()[0], 1)
            self.assertEqual(issue(station, first, old_revision), old_payload)
