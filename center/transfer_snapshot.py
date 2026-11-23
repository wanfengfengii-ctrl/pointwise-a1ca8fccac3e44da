from dataclasses import asdict

from center.cuts import Cuts
from exact import canonical_json, load_json, wire_rational

_PROVENANCE_FIELDS = {'station_id', 'issue_id', 'batch_id', 'revision_id', 'body_sha256'}


def encode_transfer_snapshot(pair_receipt_id, parents, cuts, matrix):
    return canonical_json({
        'pair_receipt_id': pair_receipt_id,
        'parents': [
            {'receipt_id': receipt_id, 'provenance': asdict(provenance)}
            for receipt_id, provenance in parents
        ],
        'cuts': [{'x': str(cut.x), 'y': str(cut.y)} for cut in cuts],
        'matrix': [[str(mass) for mass in row] for row in matrix],
    })


def _decode_parent(raw):
    if not isinstance(raw, dict) or raw.keys() != {'receipt_id', 'provenance'}:
        raise ValueError('invalid stored transfer parent')
    if type(raw['receipt_id']) is not int:
        raise ValueError('invalid stored transfer parent receipt')
    provenance = raw['provenance']
    if not isinstance(provenance, dict) or provenance.keys() != _PROVENANCE_FIELDS:
        raise ValueError('invalid stored transfer provenance')
    return {'receipt_id': raw['receipt_id'], 'provenance': dict(provenance)}


def decode_transfer_snapshot(payload):
    data = load_json(payload)
    if not isinstance(data, dict) or data.keys() != {'pair_receipt_id', 'parents', 'cuts', 'matrix'}:
        raise ValueError('invalid stored transfer report')
    if type(data['pair_receipt_id']) is not int:
        raise ValueError('invalid stored transfer pair receipt')
    parents = data['parents']
    if not isinstance(parents, list) or len(parents) != 2:
        raise ValueError('stored transfer report requires two parents')
    cuts = data['cuts']
    if not isinstance(cuts, list) or len(cuts) != 2:
        raise ValueError('stored transfer report requires two cuts')
    decoded_cuts = []
    for item in cuts:
        if not isinstance(item, dict) or item.keys() != {'x', 'y'}:
            raise ValueError('invalid stored transfer cuts')
        decoded_cuts.append(Cuts(wire_rational(item['x']), wire_rational(item['y'])))
    matrix = data['matrix']
    if not isinstance(matrix, list) or len(matrix) != 4:
        raise ValueError('stored transfer matrix requires four rows')
    decoded_matrix = []
    for row in matrix:
        if not isinstance(row, list) or len(row) != 4:
            raise ValueError('stored transfer matrix requires four columns')
        decoded_matrix.append([wire_rational(value) for value in row])
    return {
        'pair_receipt_id': data['pair_receipt_id'],
        'parents': [_decode_parent(parent) for parent in parents],
        'cuts': decoded_cuts,
        'matrix': decoded_matrix,
    }
