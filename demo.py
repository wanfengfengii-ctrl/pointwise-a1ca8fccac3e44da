from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from center.accept import accept
from center.handoff_export import export_report
from center.publish import initialize_center, publish
from center.report_lookup import read
from station.intake import import_batch
from station.issue import initialize_station, issue
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


def main():
    samples = Path(__file__).resolve().parent / 'samples'
    with TemporaryDirectory() as directory:
        for filename in ('area-correction.json', 'opposite-folds.json', 'line-and-point.json'):
            run_case(samples / filename, Path(directory))


if __name__ == '__main__':
    main()
