import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from carteis.data.migrations import current_version
from carteis.domain.errors import ValidationError
from carteis.services import BackupService, ClientService, DriverService
from carteis.services.backup import ARCHIVE_MEMBER
from tests.factories import make_client, make_driver
from tests.legacy_samples import build_legacy_db

REAL_LEGACY_DB = Path(__file__).resolve().parents[1] / "fixtures" / "legacy_bbdd.sqlite"


@pytest.fixture
def backups(conn):
    return BackupService(conn, now=lambda: datetime(2026, 10, 11, 18, 30, 5))


def _count(conn, table):
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_default_filename(backups):
    assert backups.default_filename() == "2026_10_11_18_30_05_backup.zip"


def test_backup_and_restore_round_trip(conn, backups, tmp_path):
    drivers = DriverService(conn)
    drivers.register(make_driver())
    archive = backups.create(tmp_path / "copy.zip")
    assert zipfile.ZipFile(archive).namelist() == [ARCHIVE_MEMBER]

    drivers.register(make_driver(dni="00000000T"))
    ClientService(conn).register(make_client())
    assert _count(conn, "drivers") == 2

    assert backups.restore(archive) is None
    assert _count(conn, "drivers") == 1
    assert _count(conn, "clients") == 0
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1  # connection still usable
    drivers.register(make_driver(dni="00000000T"))


def test_restore_converts_legacy_backup(conn, backups, tmp_path):
    legacy = build_legacy_db(tmp_path / "bbdd.sqlite")
    archive = tmp_path / "legacy_backup.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(legacy, "bbdd.sqlite")

    report = backups.restore(archive)
    assert report is not None
    assert report.tables["drivers"].imported == 3
    assert _count(conn, "drivers") == 3
    assert current_version(conn) >= 1


def test_restore_real_legacy_backup(conn, backups, tmp_path):
    archive = tmp_path / "old.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(REAL_LEGACY_DB, "bbdd.sqlite")
    backups.restore(archive)
    assert (_count(conn, "drivers"), _count(conn, "clients"), _count(conn, "trips")) == (19, 32, 31)


def _zip(tmp_path, members: dict[str, bytes]) -> Path:
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def _sqlite_bytes(tmp_path, setup_sql: str) -> bytes:
    path = tmp_path / "scratch.sqlite"
    path.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    db.executescript(setup_sql)
    db.close()
    return path.read_bytes()


@pytest.mark.parametrize(
    "members, message",
    [
        ({}, "único fichero"),
        ({"a.sqlite": b"x", "b.sqlite": b"y"}, "único fichero"),
        ({"../evil.sqlite": b"x"}, "contenido inesperado"),  # zip slip
        ({"dir/carteis.sqlite": b"x"}, "contenido inesperado"),
        ({"C:\\carteis.sqlite": b"x"}, "contenido inesperado"),
        ({"notes.txt": b"x"}, "contenido inesperado"),
        ({"carteis.sqlite": b"not a database at all"}, "no es una base de datos SQLite"),
    ],
)
def test_restore_rejects_bad_archives(conn, backups, tmp_path, members, message):
    DriverService(conn).register(make_driver())
    with pytest.raises(ValidationError, match=message):
        backups.restore(_zip(tmp_path, members))
    assert _count(conn, "drivers") == 1  # untouched


def test_restore_rejects_non_zip(backups, tmp_path):
    path = tmp_path / "copy.zip"
    path.write_text("hello")
    with pytest.raises(ValidationError, match="no es un fichero .zip"):
        backups.restore(path)
    with pytest.raises(ValidationError, match="no es un fichero .zip"):
        backups.restore(tmp_path / "missing.zip")


def test_restore_rejects_other_sqlite_databases(backups, tmp_path):
    data = _sqlite_bytes(tmp_path, "CREATE TABLE notes (id INTEGER);")
    with pytest.raises(ValidationError, match="no es una base de datos de CarTeis"):
        backups.restore(_zip(tmp_path, {"carteis.sqlite": data}))


def test_restore_rejects_newer_versions(backups, tmp_path):
    data = _sqlite_bytes(tmp_path, "CREATE TABLE drivers (id INTEGER); PRAGMA user_version = 999;")
    with pytest.raises(ValidationError, match="versión más reciente"):
        backups.restore(_zip(tmp_path, {"carteis.sqlite": data}))


def test_restore_rejects_oversized_member(monkeypatch, backups, tmp_path):
    monkeypatch.setattr("carteis.services.backup._MAX_DATABASE_BYTES", 10)
    with pytest.raises(ValidationError, match="demasiado grande"):
        backups.restore(_zip(tmp_path, {"carteis.sqlite": b"x" * 11}))


def test_restore_rejects_corrupt_database(conn, backups, tmp_path):
    archive = backups.create(tmp_path / "copy.zip")
    data = bytearray(zipfile.ZipFile(archive).read(ARCHIVE_MEMBER))
    data[4096:8192] = b"\xff" * 4096  # trash the second page
    with pytest.raises(ValidationError, match="dañada|no es una base de datos"):
        backups.restore(_zip(tmp_path, {"carteis.sqlite": bytes(data)}))
