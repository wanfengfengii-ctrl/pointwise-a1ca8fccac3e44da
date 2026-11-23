from dataclasses import asdict, dataclass

from center.cuts import Cuts
from center.partition_result import ZONE_ORDER, PartitionResult
from center.provenance import IssueProvenance
from exact import canonical_json, load_json, wire_rational


@dataclass(frozen=True)
class ReportSnapshot:
    receipt_id: int
    provenance: IssueProvenance
    partition: PartitionResult


def make_snapshot(receipt, result):
    return ReportSnapshot(receipt.id, receipt.provenance, result)


def encode_snapshot(snapshot):
    cuts = snapshot.partition.cuts
    return canonical_json({
        'receipt_id': snapshot.receipt_id,
        'provenance': asdict(snapshot.provenance),
        'cuts': {'x': str(cuts.x), 'y': str(cuts.y)},
        'zones': [
            {'zone': zone, 'mass': str(mass)}
            for zone, mass in zip(ZONE_ORDER, snapshot.partition.masses, strict=True)
        ],
    })


def decode_snapshot(payload):
    data = load_json(payload)
    cuts = Cuts(wire_rational(data['cuts']['x']), wire_rational(data['cuts']['y']))
    if tuple(item['zone'] for item in data['zones']) != ZONE_ORDER:
        raise ValueError('stored report has invalid zone order')
    masses = tuple(wire_rational(item['mass']) for item in data['zones'])
    return ReportSnapshot(data['receipt_id'], IssueProvenance(**data['provenance']), PartitionResult(cuts, masses))
