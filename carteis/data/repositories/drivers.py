import sqlite3

from carteis.data.converters import cents_to_money, date_from_db, date_to_db, money_to_cents
from carteis.data.database import translate_integrity_errors
from carteis.data.repositories.locations import LocationRepository
from carteis.domain.errors import NotFoundError
from carteis.domain.models import Driver
from carteis.domain.pricing import Location

_SELECT = """
    SELECT d.id, d.dni, d.surname, d.name, d.address, p.name AS province,
           m.name AS municipality, d.phone, d.salary_cents, d.licenses, d.hired_on, d.left_on
    FROM drivers d
    JOIN municipalities m ON m.id = d.municipality_id
    JOIN provinces p ON p.id = m.province_id
"""
_ORDER = " ORDER BY d.surname, d.name, d.id"
_DUPLICATE = "Ya existe un conductor con ese DNI."


class DriverRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._locations = LocationRepository(conn)

    def get(self, driver_id: int) -> Driver | None:
        row = self._conn.execute(_SELECT + " WHERE d.id = ?", (driver_id,)).fetchone()
        return _to_driver(row) if row else None

    def get_by_dni(self, dni: str) -> Driver | None:
        row = self._conn.execute(_SELECT + " WHERE d.dni = ?", (dni.strip().upper(),)).fetchone()
        return _to_driver(row) if row else None

    def list(self, active: bool | None = None) -> list[Driver]:
        """All drivers, or only active (``True``) / inactive (``False``) ones."""
        where = {None: "", True: " WHERE d.left_on IS NULL", False: " WHERE d.left_on IS NOT NULL"}
        return [_to_driver(row) for row in self._conn.execute(_SELECT + where[active] + _ORDER)]

    def add(self, driver: Driver) -> Driver:
        """Insert and set ``driver.id``. An explicit id is kept (used by the legacy import)."""
        values = self._values(driver)
        with translate_integrity_errors(_DUPLICATE):
            cursor = self._conn.execute(
                """
                INSERT INTO drivers (id, dni, surname, name, address, municipality_id, phone,
                                     salary_cents, licenses, hired_on, left_on)
                VALUES (:id, :dni, :surname, :name, :address, :municipality_id, :phone,
                        :salary_cents, :licenses, :hired_on, :left_on)
                """,
                values,
            )
        driver.id = cursor.lastrowid
        return driver

    def update(self, driver: Driver) -> None:
        if driver.id is None:
            raise ValueError("Cannot update a driver that has not been saved")
        with translate_integrity_errors(_DUPLICATE):
            cursor = self._conn.execute(
                """
                UPDATE drivers SET dni = :dni, surname = :surname, name = :name,
                    address = :address, municipality_id = :municipality_id, phone = :phone,
                    salary_cents = :salary_cents, licenses = :licenses, hired_on = :hired_on,
                    left_on = :left_on
                WHERE id = :id
                """,
                self._values(driver),
            )
        if cursor.rowcount == 0:
            raise NotFoundError("El conductor no existe.")

    def _values(self, driver: Driver) -> dict:
        return {
            "id": driver.id,
            "dni": driver.dni,
            "surname": driver.surname,
            "name": driver.name,
            "address": driver.address,
            "municipality_id": self._locations.municipality_id(
                Location(driver.province, driver.municipality)
            ),
            "phone": driver.phone,
            "salary_cents": money_to_cents(driver.salary),
            "licenses": ",".join(sorted(driver.licenses)),
            "hired_on": date_to_db(driver.hired_on),
            "left_on": date_to_db(driver.left_on),
        }


def _to_driver(row: sqlite3.Row) -> Driver:
    return Driver(
        id=row["id"],
        dni=row["dni"],
        surname=row["surname"],
        name=row["name"],
        address=row["address"],
        province=row["province"],
        municipality=row["municipality"],
        phone=row["phone"],
        salary=cents_to_money(row["salary_cents"]),
        licenses=frozenset(row["licenses"].split(",")),
        hired_on=date_from_db(row["hired_on"]),
        left_on=date_from_db(row["left_on"]),
    )
