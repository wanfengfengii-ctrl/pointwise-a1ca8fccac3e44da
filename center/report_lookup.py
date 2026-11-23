from center.report_store import ReportStore


def read(connection, report_id):
    return ReportStore(connection).load(report_id)
