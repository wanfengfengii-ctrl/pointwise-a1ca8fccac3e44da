from center.report_store import ReportStore
from center.transfer_report_store import TransferReportStore


def read(connection, report_id):
    return ReportStore(connection).load(report_id)


def read_transfer(connection, report_id):
    decoded = TransferReportStore(connection).load(report_id)
    if decoded is None:
        return None
    return {
        'report_id': report_id,
        'pair_receipt_id': decoded['pair_receipt_id'],
        'parents': decoded['parents'],
        'cuts': [{'x': cuts.x, 'y': cuts.y} for cuts in decoded['cuts']],
        'matrix': decoded['matrix'],
    }
