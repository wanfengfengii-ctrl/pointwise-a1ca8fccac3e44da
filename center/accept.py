from center.provenance import verify_provenance
from center.receipt_store import ReceiptStore
from center.received_payload import decode_station_piece


def accept(connection, station_piece):
    piece = decode_station_piece(station_piece)
    provenance = verify_provenance(piece)
    return ReceiptStore(connection).record(provenance, piece.body)
