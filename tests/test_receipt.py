import hashlib
import json
from fractions import Fraction

from center.accept import accept
from center.publish import publish
from center.receipt_store import ReceiptStore
from center.report_lookup import read
from tests import ArchiveCase, single_issue


def _changed_body(payload, edit, update_digest=True):
    data = json.loads(payload)
    edit(data['body'])
    canonical = json.dumps(data['body'], sort_keys=True, separators=(',', ':'))
    if update_digest:
        data['body_sha256'] = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return json.dumps(data)


def _translate_x(body):
    for point in body['units'][0]['vertices']:
        point[0] = str(Fraction(point[0]) + 2)


class ReceiptTests(ArchiveCase):
    def test_redelivery(self):
        with self.station() as station, self.center() as center:
            payload = single_issue(station)
            receipt = accept(center, payload)
            independently_formatted = json.dumps(json.loads(payload), indent=2)
            self.assertEqual(accept(center, independently_formatted), receipt)
            store = ReceiptStore(center)
            original = store.get(receipt)
            with self.assertRaisesRegex(ValueError, 'conflicting content'):
                accept(center, _changed_body(payload, _translate_x))
            self.assertEqual(store.get(receipt), original)
            self.assertEqual(json.loads(original.body), json.loads(payload)['body'])
            self.assertEqual(center.execute('SELECT count(*) FROM receipts').fetchone()[0], 1)

    def test_conflict_after_reopen(self):
        with self.station() as station, self.center() as center:
            payload = single_issue(station)
            envelope = json.loads(payload)
            receipt = accept(center, payload)
            with self.assertRaisesRegex(ValueError, 'conflicting content'):
                accept(center, _changed_body(payload, _translate_x))
        with self.center() as center:
            report = read(center, publish(center, receipt, 1, 1))
            self.assertEqual(report.partition.masses, (Fraction(1, 2), Fraction(1, 4), Fraction(1, 4), 0))
            self.assertEqual(report.receipt_id, receipt)
            self.assertEqual(report.provenance.station_id, envelope['station_id'])
            self.assertEqual(report.provenance.issue_id, envelope['issue_id'])
            self.assertEqual(report.provenance.body_sha256, envelope['body_sha256'])

    def test_invalid_body_or_digest_has_no_receipt(self):
        with self.station() as station, self.center() as center:
            payload = single_issue(station)
            wrong_digest = _changed_body(payload, _translate_x, update_digest=False)
            wrong_total = _changed_body(payload, lambda body: body.update(total_mass='2'))
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                accept(center, wrong_digest)
            with self.assertRaisesRegex(ValueError, 'total does not match'):
                accept(center, wrong_total)
            self.assertEqual(center.execute('SELECT count(*) FROM receipts').fetchone()[0], 0)
            self.assertEqual(accept(center, payload), 1)
