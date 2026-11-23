from dataclasses import dataclass
from fractions import Fraction

from center.provenance import IssueProvenance
from center.receipt_store import ReceiptStore
from center.received_payload import ReceivedMassUnit, decode_mass_body
from exact import load_json, sha256_text


@dataclass(frozen=True)
class ReceivedPiece:
    id: int
    provenance: IssueProvenance
    total_mass: Fraction
    units: tuple[ReceivedMassUnit, ...]


def lookup_receipt(connection, receipt_id):
    stored = ReceiptStore(connection).get(receipt_id)
    if stored is None:
        raise KeyError(f'receipt {receipt_id} not found')
    if sha256_text(stored.body) != stored.provenance.body_sha256:
        raise ValueError('stored receipt body digest mismatch')
    total_mass, units = decode_mass_body(load_json(stored.body))
    return ReceivedPiece(stored.id, stored.provenance, total_mass, units)
