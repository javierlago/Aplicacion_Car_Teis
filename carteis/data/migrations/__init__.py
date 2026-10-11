"""Versioned schema migrations.

Each ``NNNN_description.sql`` file in this package upgrades the schema to version ``NNNN``.
The current version is stored in ``PRAGMA user_version``. Never edit an applied migration:
add a new file instead.
"""

import re
import sqlite3
from importlib import resources

_MIGRATION_NAME = re.compile(r"(\d{4})_\w+\.sql")


def available() -> list[tuple[int, str]]:
    """``(version, sql)`` for every migration, in order."""
    found = []
    for entry in resources.files(__package__).iterdir():
        match = _MIGRATION_NAME.fullmatch(entry.name)
        if match:
            found.append((int(match[1]), entry.read_text(encoding="utf-8")))
    return sorted(found)


def current_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations, each one atomically. Returns the resulting version."""
    version = current_version(conn)
    for target, sql in available():
        if target <= version:
            continue
        try:
            conn.executescript(f"BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version = {target};\nCOMMIT;")
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        version = target
    return version
