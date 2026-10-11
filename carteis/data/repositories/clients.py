import sqlite3

from carteis.data.converters import date_from_db, date_to_db
from carteis.data.database import translate_integrity_errors
from carteis.data.repositories.locations import LocationRepository
from carteis.domain.errors import NotFoundError
from carteis.domain.models import Client
from carteis.domain.pricing import Location

_SELECT = """
    SELECT c.id, c.dni, c.company_name, c.address, p.name AS province,
           m.name AS municipality, c.phone, c.left_on
    FROM clients c
    JOIN municipalities m ON m.id = c.municipality_id
    JOIN provinces p ON p.id = m.province_id
"""
_ORDER = " ORDER BY c.company_name, c.id"
_DUPLICATE = "Ya existe un cliente con ese DNI."


class ClientRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._locations = LocationRepository(conn)

    def get(self, client_id: int) -> Client | None:
        row = self._conn.execute(_SELECT + " WHERE c.id = ?", (client_id,)).fetchone()
        return _to_client(row) if row else None

    def get_by_dni(self, dni: str) -> Client | None:
        row = self._conn.execute(_SELECT + " WHERE c.dni = ?", (dni.strip().upper(),)).fetchone()
        return _to_client(row) if row else None

    def list(self, active: bool | None = None) -> list[Client]:
        """All clients, or only active (``True``) / inactive (``False``) ones."""
        where = {None: "", True: " WHERE c.left_on IS NULL", False: " WHERE c.left_on IS NOT NULL"}
        return [_to_client(row) for row in self._conn.execute(_SELECT + where[active] + _ORDER)]

    def add(self, client: Client) -> Client:
        """Insert and set ``client.id``. An explicit id is kept (used by the legacy import)."""
        with translate_integrity_errors(_DUPLICATE):
            cursor = self._conn.execute(
                """
                INSERT INTO clients (id, dni, company_name, address, municipality_id, phone,
                                     left_on)
                VALUES (:id, :dni, :company_name, :address, :municipality_id, :phone, :left_on)
                """,
                self._values(client),
            )
        client.id = cursor.lastrowid
        return client

    def update(self, client: Client) -> None:
        if client.id is None:
            raise ValueError("Cannot update a client that has not been saved")
        with translate_integrity_errors(_DUPLICATE):
            cursor = self._conn.execute(
                """
                UPDATE clients SET dni = :dni, company_name = :company_name,
                    address = :address, municipality_id = :municipality_id, phone = :phone,
                    left_on = :left_on
                WHERE id = :id
                """,
                self._values(client),
            )
        if cursor.rowcount == 0:
            raise NotFoundError("El cliente no existe.")

    def _values(self, client: Client) -> dict:
        return {
            "id": client.id,
            "dni": client.dni,
            "company_name": client.company_name,
            "address": client.address,
            "municipality_id": self._locations.municipality_id(
                Location(client.province, client.municipality)
            ),
            "phone": client.phone,
            "left_on": date_to_db(client.left_on),
        }


def _to_client(row: sqlite3.Row) -> Client:
    return Client(
        id=row["id"],
        dni=row["dni"],
        company_name=row["company_name"],
        address=row["address"],
        province=row["province"],
        municipality=row["municipality"],
        phone=row["phone"],
        left_on=date_from_db(row["left_on"]),
    )
