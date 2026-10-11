import sqlite3

from carteis.domain.errors import ValidationError
from carteis.domain.pricing import Location


class LocationRepository:
    """Read-only access to the provinces and municipalities reference data."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def provinces(self) -> list[str]:
        return [row["name"] for row in self._conn.execute("SELECT name FROM provinces ORDER BY id")]

    def municipalities(self, province: str) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT m.name FROM municipalities m JOIN provinces p ON p.id = m.province_id
            WHERE p.name = ? ORDER BY m.id
            """,
            (province,),
        )
        return [row["name"] for row in rows]

    def provinces_of(self, municipality: str) -> list[str]:
        """Provinces that have a municipality with this name (some names repeat)."""
        rows = self._conn.execute(
            """
            SELECT p.name FROM municipalities m JOIN provinces p ON p.id = m.province_id
            WHERE m.name = ? ORDER BY p.id
            """,
            (municipality,),
        )
        return [row["name"] for row in rows]

    def municipality_id(self, location: Location) -> int:
        row = self._conn.execute(
            """
            SELECT m.id FROM municipalities m JOIN provinces p ON p.id = m.province_id
            WHERE p.name = ? AND m.name = ?
            """,
            (location.province, location.municipality),
        ).fetchone()
        if row is None:
            raise ValidationError(
                f"La localidad «{location.municipality}» no existe en la provincia "
                f"«{location.province}».",
                field="municipality",
            )
        return row["id"]
