from dataclasses import dataclass
from fractions import Fraction

from center.pair_payload import JointUnit, decode_joint_body
from center.pair_receipt_store import PairReceiptStore
from exact import load_json, sha256_text


@dataclass(frozen=True)
class ReceivedPair:
    id: int
    old_receipt_id: int
    new_receipt_id: int
    total_mass: Fraction
    units: tuple[JointUnit, ...]


def lookup_pair_receipt(connection, pair_receipt_id):
    stored = PairReceiptStore(connection).get(pair_receipt_id)
    if stored is None:
        raise KeyError(f'pair receipt {pair_receipt_id} not found')
    if sha256_text(stored.body) != stored.body_sha256:
        raise ValueError('stored pair evidence digest mismatch')
    total_mass, units = decode_joint_body(load_json(stored.body))
    return ReceivedPair(stored.id, stored.old_receipt_id, stored.new_receipt_id, total_mass, units)
