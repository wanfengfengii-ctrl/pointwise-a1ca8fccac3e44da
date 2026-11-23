from dataclasses import dataclass

from exact import require_id, require_station_id, sha256_text


@dataclass(frozen=True)
class IssueProvenance:
    station_id: str
    issue_id: int
    batch_id: int
    revision_id: int
    body_sha256: str

    @property
    def identity(self):
        return self.station_id, self.issue_id


def verify_provenance(piece):
    station_id = require_station_id(piece.station_id)
    issue_id = require_id(piece.issue_id, 'issue id')
    batch_id = require_id(piece.batch_id, 'batch id')
    revision_id = require_id(piece.revision_id, 'revision id')
    if piece.body_sha256 != sha256_text(piece.body):
        raise ValueError('station piece body digest mismatch')
    return IssueProvenance(station_id, issue_id, batch_id, revision_id, piece.body_sha256)


def same_issue_content(original, original_body, incoming, incoming_body):
    return original == incoming and original_body == incoming_body
