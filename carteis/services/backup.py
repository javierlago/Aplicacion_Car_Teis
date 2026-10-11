"""Zip backups of the live database (fixes bug D8).

Backups are taken and restored with SQLite's online backup API, so the database can stay
open, and the archive is validated before anything is overwritten. Archives made by the
legacy app (``bbdd.sqlite`` with the Spanish schema) are converted on restore.
"""

import sqlite3
import zipfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from carteis.data import migrations
from carteis.data.database import connect
from carteis.data.legacy_import import ImportReport, import_legacy
from carteis.domain.errors import ValidationError

ARCHIVE_MEMBER = "carteis.sqlite"
_DATABASE_SUFFIXES = (".sqlite", ".db")
_MAX_DATABASE_BYTES = 500 * 1024 * 1024
_NEW_SCHEMA_TABLES = {"drivers", "clients", "invoices", "trips"}
_LEGACY_SCHEMA_TABLES = {"drivers", "listadoClientes", "facturas", "viajes"}


class BackupService:
    def __init__(self, conn: sqlite3.Connection, now: Callable[[], datetime] = datetime.now):
        self._conn = conn
        self._now = now

    def default_filename(self) -> str:
        return f"{self._now():%Y_%m_%d_%H_%M_%S}_backup.zip"

    def create(self, destination: Path) -> Path:
        """Write a consistent snapshot of the database to ``destination`` (a .zip file)."""
        with TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / ARCHIVE_MEMBER
            target = sqlite3.connect(snapshot)
            try:
                self._conn.backup(target)
            finally:
                target.close()
            with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(snapshot, ARCHIVE_MEMBER)
        return destination

    def restore(self, archive_path: Path) -> ImportReport | None:
        """Replace the database contents with the backup in ``archive_path``.

        Returns the conversion report when the backup came from the legacy app.
        Raises ``ValidationError`` (and changes nothing) if the archive is not a valid backup.
        """
        with TemporaryDirectory() as tmp:
            candidate = _extract_database(archive_path, Path(tmp) / "backup.sqlite")
            report = None
            match _schema_of(candidate):
                case "legacy":
                    converted = Path(tmp) / "converted.sqlite"
                    report = import_legacy(candidate, converted)
                    candidate = converted
                case "current":
                    pass

            source = connect(candidate)
            try:
                migrations.migrate(source)
                source.backup(self._conn)
            finally:
                source.close()
        return report


def _invalid(reason: str) -> ValidationError:
    return ValidationError(f"La copia de seguridad no es válida: {reason}")


def _extract_database(archive_path: Path, destination: Path) -> Path:
    """Copy the single database file out of the archive without trusting its paths."""
    try:
        with zipfile.ZipFile(archive_path) as archive:
            files = [info for info in archive.infolist() if not info.is_dir()]
            if len(files) != 1:
                raise _invalid("debe contener un único fichero de base de datos.")
            member = files[0]
            name = PurePosixPath(member.filename.replace("\\", "/"))
            if len(name.parts) != 1 or name.suffix not in _DATABASE_SUFFIXES:
                raise _invalid(f"contenido inesperado «{member.filename}».")
            if member.file_size > _MAX_DATABASE_BYTES:
                raise _invalid("el fichero es demasiado grande.")
            destination.write_bytes(archive.read(member))
    except (zipfile.BadZipFile, OSError) as error:
        raise _invalid("no es un fichero .zip legible.") from error
    return destination


def _schema_of(path: Path) -> str:
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise _invalid("la base de datos está dañada.")
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
            version = migrations.current_version(conn)
        finally:
            conn.close()
    except sqlite3.DatabaseError as error:
        raise _invalid("el fichero no es una base de datos SQLite.") from error

    latest = migrations.available()[-1][0]
    if version > latest:
        raise _invalid("se creó con una versión más reciente de la aplicación.")
    if version >= 1 and _NEW_SCHEMA_TABLES.issubset(tables):
        return "current"
    if version == 0 and _LEGACY_SCHEMA_TABLES.issubset(tables):
        return "legacy"
    raise _invalid("no es una base de datos de CarTeis.")
