from archive import enable_foreign_keys, write_transaction
from center.cuts import parse_cuts
from center.mass_partition import partition_mass
from center.pair_lookup import lookup_pair_receipt
from center.pair_receipt_store import PairReceiptStore
from center.receipt_lookup import lookup_receipt
from center.receipt_store import ReceiptStore
from center.report_snapshot import make_snapshot
from center.report_store import ReportStore
from center.transfer_matrix import require_conserved_transfer, transfer_matrix
from center.transfer_report_store import TransferReportStore
from center.transfer_snapshot import encode_transfer_snapshot


def initialize_center(connection):
    enable_foreign_keys(connection)
    with write_transaction(connection):
        ReceiptStore(connection).initialize()
        ReportStore(connection).initialize()
        PairReceiptStore(connection).initialize()
        TransferReportStore(connection).initialize()


def publish(connection, receipt_id, x_cut, y_cut):
    cuts = parse_cuts(x_cut, y_cut)
    receipt = lookup_receipt(connection, receipt_id)
    result = partition_mass(receipt, cuts)
    return ReportStore(connection).save(make_snapshot(receipt, result))


def publish_transfer(connection, pair_receipt_id, old_x_cut, old_y_cut, new_x_cut, new_y_cut):
    old_cuts = parse_cuts(old_x_cut, old_y_cut)
    new_cuts = parse_cuts(new_x_cut, new_y_cut)
    pair = lookup_pair_receipt(connection, pair_receipt_id)
    matrix = transfer_matrix(pair.units, old_cuts, new_cuts)
    require_conserved_transfer(matrix, pair.total_mass)
    parents = []
    for receipt_id, cuts, marginals in (
        (pair.old_receipt_id, old_cuts, [sum(row) for row in matrix]),
        (pair.new_receipt_id, new_cuts, [sum(column) for column in zip(*matrix)]),
    ):
        receipt = lookup_receipt(connection, receipt_id)
        if tuple(marginals) != partition_mass(receipt, cuts).masses:
            raise ValueError('transfer marginals do not match the parent partition')
        parents.append((receipt.id, receipt.provenance))
    snapshot = encode_transfer_snapshot(pair.id, parents, (old_cuts, new_cuts), matrix)
    return TransferReportStore(connection).save(pair.id, snapshot)
