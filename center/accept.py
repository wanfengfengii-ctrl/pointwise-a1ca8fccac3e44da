from center.pair_payload import decode_pair_piece, derive_edition_body
from center.pair_receipt_store import PairReceiptStore
from center.provenance import verify_provenance
from center.receipt_store import ReceiptStore
from center.received_payload import decode_station_piece
from exact import canonical_json, require_id, sha256_text


def accept(connection, station_piece):
    piece = decode_station_piece(station_piece)
    provenance = verify_provenance(piece)
    return ReceiptStore(connection).record(provenance, piece.body)


def accept_pair(connection, pair_piece, old_receipt_id, new_receipt_id):
    require_id(old_receipt_id, 'receipt id')
    require_id(new_receipt_id, 'receipt id')
    piece = decode_pair_piece(pair_piece)
    receipts = ReceiptStore(connection)
    parents = []
    for receipt_id, parent in ((old_receipt_id, piece.parents[0]), (new_receipt_id, piece.parents[1])):
        receipt = receipts.get(receipt_id)
        if receipt is None:
            raise KeyError(f'receipt {receipt_id} not found')
        if sha256_text(receipt.body) != receipt.provenance.body_sha256:
            raise ValueError('stored receipt body digest mismatch')
        if receipt.provenance != parent:
            raise ValueError('pair parent does not match the cited receipt')
        parents.append(receipt)
    old, new = piece.parents
    if old.station_id != new.station_id or old.batch_id != new.batch_id:
        raise ValueError('pair parents must share one station and one batch')
    if old.revision_id == new.revision_id:
        raise ValueError('a transfer pair requires two different revisions')
    for edition, receipt in (('old', parents[0]), ('new', parents[1])):
        if canonical_json(derive_edition_body(piece.units, edition)) != receipt.body:
            raise ValueError(f'pair evidence does not reproduce the {edition} edition')
    return PairReceiptStore(connection).record(piece, old_receipt_id, new_receipt_id)
