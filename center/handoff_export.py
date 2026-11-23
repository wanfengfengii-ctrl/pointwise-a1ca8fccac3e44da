from center.report_lookup import read
from center.report_snapshot import encode_snapshot
from exact import canonical_json, load_json


def export_report(connection, report_id):
    snapshot = read(connection, report_id)
    if snapshot is None:
        return None
    data = load_json(encode_snapshot(snapshot))
    data['report_id'] = report_id
    return canonical_json(data)
