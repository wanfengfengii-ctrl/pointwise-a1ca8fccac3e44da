import json
from fractions import Fraction as F

from center.accept import accept
from center.handoff_export import export_report
from center.publish import publish
from center.report_lookup import read
from station.intake import import_batch
from station.issue import issue
from station.revisions import revise
from tests import ArchiveCase, FOLD_LEFT, FOLD_RIGHT, IDENTITY, POINT_ON_CUTS, piece, single_issue


class PartitionTests(ArchiveCase):
    def test_offline_reopen(self):
        with self.station() as station, self.center() as center:
            receipt = accept(center, single_issue(station))
        with self.center() as center:
            report = read(center, publish(center, receipt, 1, 1))
            self.assertEqual(report.partition.masses, (F(1, 2), F(1, 4), F(1, 4), 0))
            self.assertEqual(report.receipt_id, receipt)

    def test_invalid_cut(self):
        with self.station() as station, self.center() as center:
            receipt = accept(center, single_issue(station))
        with self.center() as center:
            for bad_cut in ('not a rational', '1/0', None, 1.0, True):
                with self.subTest(cut=bad_cut), self.assertRaises(ValueError):
                    publish(center, receipt, bad_cut, 1)
            with self.assertRaises(KeyError):
                publish(center, 999, 1, 1)
            self.assertEqual(center.execute('SELECT count(*) FROM reports').fetchone()[0], 0)
            self.assertEqual(center.execute('SELECT count(*) FROM report_signatures').fetchone()[0], 0)

    def test_folded_quartets(self):
        with self.station() as station, self.center() as center:
            payloads = [single_issue(station, calibration=calibration) for calibration in (FOLD_LEFT, FOLD_RIGHT)]
            receipts = [accept(center, payload) for payload in payloads]
        with self.center() as center:
            ids = [publish(center, receipt, 1, 1) for receipt in receipts]
        with self.center() as center:
            reports = [read(center, report_id) for report_id in ids]
            exports = [json.loads(export_report(center, report_id)) for report_id in ids]
        expected = [(F(3, 4), F(1, 4), F(0), F(0)), (F(1, 4), F(3, 4), F(0), F(0))]
        actual = [report.partition.masses for report in reports]
        self.assertEqual(actual, expected, 'FOLDED_QUARTET_MASS_MISMATCH')
        expected_handoffs = []
        actual_handoffs = []
        for receipt, payload, masses, report, exported in zip(receipts, payloads, expected, reports, exports, strict=True):
            envelope = json.loads(payload)
            self.assertEqual(report.receipt_id, receipt)
            self.assertEqual(report.provenance.revision_id, envelope['revision_id'])
            self.assertEqual(report.provenance.body_sha256, envelope['body_sha256'])
            expected_handoffs.append({
                'receipt_id': receipt, 'body_sha256': envelope['body_sha256'],
                'zones': [{'zone': name, 'mass': str(mass)} for name, mass in zip(('LL', 'HL', 'LH', 'HH'), masses)],
            })
            actual_handoffs.append({
                'receipt_id': exported['receipt_id'], 'body_sha256': exported['provenance']['body_sha256'],
                'zones': exported['zones'],
            })
        self.assertEqual(actual_handoffs, expected_handoffs)
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'v6.folded_quartets',
            'input': {'triangle': [[0, 0], [2, 0], [0, 2]], 'mass': '1',
                      'calibrations': [FOLD_LEFT, FOLD_RIGHT], 'cuts': [1, 1]},
            'expected': [[str(mass) for mass in row] for row in expected],
            'actual': [[str(mass) for mass in row] for row in actual],
            'downstream_expected': expected_handoffs,
            'downstream_actual': actual_handoffs,
            'code_paths': ['station/freeze.py', 'station/issue.py', 'center/accept.py',
                           'center/receipt_lookup.py', 'center/mass_partition.py',
                           'center/publish.py', 'center/handoff_export.py'],
            'oracle': 'The source triangle has area 2. The part with source x greater than 1 has area 1/2. '
                      'The two affine maps exchange those source portions; both images lie below the y cut.',
        }, sort_keys=True))

    def _boundary_receipt(self, include_area):
        pieces = [piece('rising', '1/2'), piece('falling', '1/2'), piece('point')]
        calibrations = {
            'rising': [[0, 0, 1], [1, 0, 0]],
            'falling': [[0, 0, 1], [-1, 0, 2]],
            'point': POINT_ON_CUTS,
        }
        if include_area:
            pieces.append(piece('area'))
            calibrations['area'] = IDENTITY
        with self.station() as station, self.center() as center:
            batch = import_batch(station, pieces)
            revision = revise(station, batch, calibrations)
            return accept(center, issue(station, batch, revision))

    def test_uniform_line_and_point(self):
        receipt = self._boundary_receipt(include_area=False)
        with self.center() as center:
            report = read(center, publish(center, receipt, 1, 1))
            self.assertEqual(report.partition.masses, (0, F(1, 2), 0, F(3, 2)))
            self.assertEqual(sum(report.partition.masses), 2)

    def test_mixed_support(self):
        receipt = self._boundary_receipt(include_area=True)
        with self.center() as center:
            report = read(center, publish(center, receipt, 1, 1))
            self.assertEqual(report.partition.masses, (F(1, 2), F(3, 4), F(1, 4), F(3, 2)))
            self.assertEqual(sum(report.partition.masses), 3)

    def test_diagonal_line_with_interior_density_knot(self):
        calibration = [[1, '1/2', 0], [-1, '-1/2', 2]]
        with self.station() as station, self.center() as center:
            receipt = accept(center, single_issue(station, calibration=calibration))
        with self.center() as center:
            report = read(center, publish(center, receipt, '1/2', 1))
            # The first quarter of the segment corresponds to a triangle scaled
            # by 1/4 and 1/2 along the two source edges. Half the mass lies past x=1.
            self.assertEqual(report.partition.masses, (0, F(1, 2), F(1, 8), F(3, 8)))
