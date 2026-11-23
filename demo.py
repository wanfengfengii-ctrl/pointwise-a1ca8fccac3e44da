from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from center.accept import accept, accept_pair
from center.handoff_export import export_report, export_transfer
from center.publish import initialize_center, publish, publish_transfer
from center.report_lookup import read, read_transfer
from station.intake import import_batch
from station.issue import initialize_station, issue, issue_pair
from station.revisions import revise


def run_case(sample_path, directory):
    sample = json.loads(sample_path.read_text(encoding='utf-8'))
    station_path = directory / (sample_path.stem + '-station.sqlite')
    center_path = directory / (sample_path.stem + '-center.sqlite')
    accepted = []
    with closing(sqlite3.connect(station_path)) as station, closing(sqlite3.connect(center_path)) as center:
        initialize_station(station, 'demo-' + sample_path.stem)
        initialize_center(center)
        batch = import_batch(station, sample['pieces'])
        for entry in sample['revisions']:
            revision = revise(station, batch, entry['calibrations'])
            payload = issue(station, batch, revision)
            accepted.append((accept(center, payload), revision, entry['expected']))

    with closing(sqlite3.connect(center_path)) as center:
        initialize_center(center)
        report_ids = [publish(center, receipt_id, *sample['cuts']) for receipt_id, _, _ in accepted]

    with closing(sqlite3.connect(center_path)) as center:
        initialize_center(center)
        for report_id, (receipt_id, revision, expected) in zip(report_ids, accepted, strict=True):
            report = read(center, report_id)
            if report is None:
                raise RuntimeError(f'{sample["case_id"]}: missing report {report_id}')
            actual = [str(mass) for mass in report.partition.masses]
            if actual != expected or report.receipt_id != receipt_id or report.provenance.revision_id != revision:
                raise RuntimeError(f'{sample["case_id"]}: unexpected report {report_id}, partitions {actual}')
            exported = json.loads(export_report(center, report_id))
            print(json.dumps({'case_id': sample['case_id'], 'report': exported}, sort_keys=True))


def run_transfer_case(directory):
    """Two pairs with identical single-edition accounts sign different matrices."""
    pieces = [{'name': 'panel-transfer', 'vertices': [[0, 0], [2, 0], [0, 2]], 'mass': '1'}]
    calibrations = {
        'old': [[1, 0, 0], [0, 0, 0]],
        'aligned': [[1, 0, 0], [0, 0, 0]],
        'crossed': [[0, 1, 0], [0, 0, 0]],
    }
    station_path = directory / 'transfer-station.sqlite'
    center_path = directory / 'transfer-center.sqlite'
    with closing(sqlite3.connect(station_path)) as station, closing(sqlite3.connect(center_path)) as center:
        initialize_station(station, 'demo-transfer')
        initialize_center(center)
        batch = import_batch(station, pieces)
        issued = {}
        for label, calibration in calibrations.items():
            revision = revise(station, batch, {'panel-transfer': calibration})
            payload = issue(station, batch, revision)
            issued[label] = (revision, accept(center, payload))
        pair_receipts = {}
        for label in ('aligned', 'crossed'):
            pair = issue_pair(station, batch, issued['old'][0], issued[label][0])
            pair_receipts[label] = accept_pair(center, pair, issued['old'][1], issued[label][1])

    # The station archive is closed; the center signs from the accepted evidence.
    with closing(sqlite3.connect(center_path)) as center:
        initialize_center(center)
        single_reports = {label: publish(center, receipt, 1, 1) for label, (_, receipt) in issued.items()}
        transfer_reports = {label: publish_transfer(center, pair_receipt, 1, 1, 1, 1)
                            for label, pair_receipt in pair_receipts.items()}

    with closing(sqlite3.connect(center_path)) as center:
        initialize_center(center)
        zones = [[str(mass) for mass in read(center, report_id).partition.masses]
                 for report_id in single_reports.values()]
        if len({tuple(zone) for zone in zones}) != 1:
            raise RuntimeError('transfer demo: expected identical single-edition accounts')
        exported = {}
        for label, report_id in transfer_reports.items():
            report = read_transfer(center, report_id)
            if report is None:
                raise RuntimeError(f'transfer demo: missing report {report_id}')
            row_sums = [str(sum(row)) for row in report['matrix']]
            column_sums = [str(sum(column)) for column in zip(*report['matrix'])]
            if row_sums != zones[0] or column_sums != zones[0]:
                raise RuntimeError(f'transfer demo: marginals mismatch for {label}')
            exported[label] = json.loads(export_transfer(center, report_id))
        expected = {
            'aligned': [['3/4', '0', '0', '0'], ['0', '1/4', '0', '0'],
                        ['0', '0', '0', '0'], ['0', '0', '0', '0']],
            'crossed': [['1/2', '1/4', '0', '0'], ['1/4', '0', '0', '0'],
                        ['0', '0', '0', '0'], ['0', '0', '0', '0']],
        }
        for label, matrix in expected.items():
            if exported[label]['matrix'] != matrix:
                raise RuntimeError(f'transfer demo: unexpected matrix for {label}')
        print(json.dumps({
            'case_id': 'transfer.shared-marginals',
            'single_edition_zones': zones[0],
            'transfers': exported,
        }, sort_keys=True))


def main():
    samples = Path(__file__).resolve().parent / 'samples'
    with TemporaryDirectory() as directory:
        for filename in ('area-correction.json', 'opposite-folds.json', 'line-and-point.json'):
            run_case(samples / filename, Path(directory))
        run_transfer_case(Path(directory))


if __name__ == '__main__':
    main()
