from archive import enable_foreign_keys, write_transaction
from exact import load_json, require_id, require_station_id
from station.batch_store import BatchStore
from station.calibration import map_vertices
from station.freeze import freeze_revision
from station.issue_payload import (
    encode_joint_body,
    encode_mass_body,
    encode_pair_piece,
    encode_station_piece,
)
from station.revisions import RevisionStore


class IssueStore:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self, station_id=None):
        if station_id is not None:
            require_station_id(station_id)
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS station_identity (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                station_id TEXT NOT NULL
            )
        ''')
        row = self.connection.execute('SELECT station_id FROM station_identity WHERE singleton = 1').fetchone()
        if row is None:
            if station_id is None:
                raise ValueError('a new station archive requires a station identifier')
            self.connection.execute('INSERT INTO station_identity VALUES (1, ?)', (station_id,))
        elif station_id is not None and station_id != row[0]:
            raise ValueError('station identifier does not match this archive')
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY,
                batch_id INTEGER NOT NULL,
                revision_id INTEGER NOT NULL UNIQUE,
                payload TEXT NOT NULL,
                FOREIGN KEY (batch_id, revision_id) REFERENCES revisions(batch_id, id)
            )
        ''')

    def get(self, batch_id, revision_id):
        require_id(batch_id, 'batch id')
        require_id(revision_id, 'revision id')
        row = self.connection.execute(
            'SELECT payload FROM issues WHERE batch_id = ? AND revision_id = ?', (batch_id, revision_id)
        ).fetchone()
        return None if row is None else row[0]

    def save(self, batch_id, revision_id, body):
        with write_transaction(self.connection):
            existing = self.get(batch_id, revision_id)
            if existing is not None:
                return existing
            station_id = self.connection.execute(
                'SELECT station_id FROM station_identity WHERE singleton = 1'
            ).fetchone()[0]
            issue_id = self.connection.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM issues').fetchone()[0]
            payload = encode_station_piece(station_id, issue_id, batch_id, revision_id, body)
            self.connection.execute(
                'INSERT INTO issues (id, batch_id, revision_id, payload) VALUES (?, ?, ?, ?)',
                (issue_id, batch_id, revision_id, payload),
            )
        return payload


class PairIssueStore:
    def __init__(self, connection):
        self.connection = connection

    def initialize(self):
        self.connection.execute('''
            CREATE TABLE IF NOT EXISTS pair_issues (
                id INTEGER PRIMARY KEY,
                batch_id INTEGER NOT NULL,
                old_revision_id INTEGER NOT NULL,
                new_revision_id INTEGER NOT NULL,
                payload TEXT NOT NULL,
                UNIQUE (batch_id, old_revision_id, new_revision_id),
                FOREIGN KEY (batch_id, old_revision_id) REFERENCES revisions(batch_id, id),
                FOREIGN KEY (batch_id, new_revision_id) REFERENCES revisions(batch_id, id)
            )
        ''')

    def get(self, batch_id, old_revision_id, new_revision_id):
        row = self.connection.execute(
            'SELECT payload FROM pair_issues '
            'WHERE batch_id = ? AND old_revision_id = ? AND new_revision_id = ?',
            (batch_id, old_revision_id, new_revision_id),
        ).fetchone()
        return None if row is None else row[0]

    def save(self, batch_id, old_revision_id, new_revision_id, payload):
        with write_transaction(self.connection):
            existing = self.get(batch_id, old_revision_id, new_revision_id)
            if existing is not None:
                return existing
            self.connection.execute(
                'INSERT INTO pair_issues (batch_id, old_revision_id, new_revision_id, payload) '
                'VALUES (?, ?, ?, ?)',
                (batch_id, old_revision_id, new_revision_id, payload),
            )
        return payload


def initialize_station(connection, station_id=None):
    enable_foreign_keys(connection)
    with write_transaction(connection):
        BatchStore(connection).initialize()
        RevisionStore(connection).initialize()
        IssueStore(connection).initialize(station_id)
        PairIssueStore(connection).initialize()


def issue(connection, batch_id, revision_id):
    store = IssueStore(connection)
    existing = store.get(batch_id, revision_id)
    if existing is not None:
        return existing
    revision = RevisionStore(connection).get(batch_id, revision_id)
    batch = BatchStore(connection).load(batch_id)
    return store.save(batch_id, revision_id, encode_mass_body(freeze_revision(batch, revision)))


def issue_pair(connection, batch_id, old_revision_id, new_revision_id):
    require_id(batch_id, 'batch id')
    require_id(old_revision_id, 'revision id')
    require_id(new_revision_id, 'revision id')
    if old_revision_id == new_revision_id:
        raise ValueError('a transfer pair requires two different revisions')
    store = PairIssueStore(connection)
    existing = store.get(batch_id, old_revision_id, new_revision_id)
    if existing is not None:
        return existing
    batch = BatchStore(connection).load(batch_id)
    revisions = RevisionStore(connection)
    old_revision = revisions.get(batch_id, old_revision_id)
    new_revision = revisions.get(batch_id, new_revision_id)
    issues = IssueStore(connection)
    parents = []
    for revision_id in (old_revision_id, new_revision_id):
        payload = issues.get(batch_id, revision_id)
        if payload is None:
            raise KeyError(f'revision {revision_id} not issued for batch {batch_id}')
        envelope = load_json(payload)
        parents.append({field: envelope[field] for field in
                        ('station_id', 'issue_id', 'batch_id', 'revision_id', 'body_sha256')})
    body = encode_joint_body(
        (piece.mass,
         map_vertices(piece.triangle, old_revision.calibrations[piece.name]),
         map_vertices(piece.triangle, new_revision.calibrations[piece.name]))
        for piece in batch.pieces
    )
    return store.save(batch_id, old_revision_id, new_revision_id, encode_pair_piece(parents, body))
