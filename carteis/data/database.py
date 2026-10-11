"""Connection setup, explicit transactions and SQLite error translation."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from carteis.domain.errors import DuplicateError, NotFoundError


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the database with foreign keys enforced (fixes bug D4: cascades were ignored).

    The connection runs in autocommit mode: single statements commit on their own, and
    multi-statement writes go through :func:`transaction`.
    """
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Run the block atomically. Nested calls join the outer transaction."""
    if conn.in_transaction:
        yield
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


@contextmanager
def translate_integrity_errors(duplicate_message: str) -> Iterator[None]:
    """Turn constraint violations the user can cause into domain errors."""
    try:
        yield
    except sqlite3.IntegrityError as error:
        message = str(error)
        if message.startswith("UNIQUE constraint failed"):
            raise DuplicateError(duplicate_message) from error
        if message.startswith("FOREIGN KEY constraint failed"):
            raise NotFoundError("Un registro relacionado no existe.") from error
        raise
