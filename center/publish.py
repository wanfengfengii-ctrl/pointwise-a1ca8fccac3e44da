from archive import enable_foreign_keys, write_transaction
from center.cuts import parse_cuts
from center.mass_partition import partition_mass
from center.receipt_lookup import lookup_receipt
from center.receipt_store import ReceiptStore
from center.report_snapshot import make_snapshot
from center.report_store import ReportStore


def initialize_center(connection):
    enable_foreign_keys(connection)
    with write_transaction(connection):
        ReceiptStore(connection).initialize()
        ReportStore(connection).initialize()


def publish(connection, receipt_id, x_cut, y_cut):
    cuts = parse_cuts(x_cut, y_cut)
    receipt = lookup_receipt(connection, receipt_id)
    result = partition_mass(receipt, cuts)
    return ReportStore(connection).save(make_snapshot(receipt, result))
