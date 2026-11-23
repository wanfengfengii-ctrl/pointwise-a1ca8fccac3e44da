from archive import enable_foreign_keys, write_transaction
from exact import require_id, require_station_id
from station.batch_store import BatchStore
from station.freeze import freeze_revision
from station.issue_payload import encode_mass_body, encode_station_piece
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


def initialize_station(connection, station_id=None):
    enable_foreign_keys(connection)
    with write_transaction(connection):
        BatchStore(connection).initialize()
        RevisionStore(connection).initialize()
        IssueStore(connection).initialize(station_id)


def issue(connection, batch_id, revision_id):
    store = IssueStore(connection)
    existing = store.get(batch_id, revision_id)
    if existing is not None:
        return existing
    revision = RevisionStore(connection).get(batch_id, revision_id)
    batch = BatchStore(connection).load(batch_id)
    return store.save(batch_id, revision_id, encode_mass_body(freeze_revision(batch, revision)))
