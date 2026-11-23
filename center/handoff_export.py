from center.report_lookup import read, read_transfer
from center.report_snapshot import encode_snapshot
from exact import canonical_json, load_json


def export_report(connection, report_id):
    snapshot = read(connection, report_id)
    if snapshot is None:
        return None
    data = load_json(encode_snapshot(snapshot))
    data['report_id'] = report_id
    return canonical_json(data)


def export_transfer(connection, report_id):
    report = read_transfer(connection, report_id)
    if report is None:
        return None
    return canonical_json({
        **report,
        'cuts': [{'x': str(cut['x']), 'y': str(cut['y'])} for cut in report['cuts']],
        'matrix': [[str(mass) for mass in row] for row in report['matrix']],
    })
