from contextlib import contextmanager


def enable_foreign_keys(connection):
    if connection.in_transaction:
        raise ValueError('initialize the archive on an idle connection')
    connection.execute('PRAGMA foreign_keys = ON')


@contextmanager
def write_transaction(connection):
    connection.execute('BEGIN IMMEDIATE')
    with connection:
        yield
