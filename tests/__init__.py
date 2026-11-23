from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest import TestCase

from center.publish import initialize_center
from station.issue import initialize_station, issue
from station.intake import import_batch
from station.revisions import revise


IDENTITY = [[1, 0, 0], [0, 1, 0]]
FOLD_LEFT = [[1, 0, 0], [0, 0, 0]]
FOLD_RIGHT = [[-1, 0, 2], [0, 0, 0]]
POINT_ON_CUTS = [[0, 0, 1], [0, 0, 1]]


def piece(name='panel', mass=1):
    return {'name': name, 'vertices': [[0, 0], [2, 0], [0, 2]], 'mass': mass}


def single_issue(connection, mass=1, calibration=IDENTITY):
    batch = import_batch(connection, [piece(mass=mass)])
    revision = revise(connection, batch, {'panel': calibration})
    return issue(connection, batch, revision)


class ArchiveCase(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    @contextmanager
    def station(self):
        with closing(sqlite3.connect(self.root / 'station.sqlite')) as connection:
            initialize_station(connection, 'test-station')
            yield connection

    @contextmanager
    def center(self):
        with closing(sqlite3.connect(self.root / 'center.sqlite')) as connection:
            initialize_center(connection)
            yield connection
