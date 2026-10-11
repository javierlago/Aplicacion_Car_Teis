import sqlite3
from collections import defaultdict

from carteis.data.converters import cents_to_money, date_from_db, date_to_db, money_to_cents
from carteis.data.database import transaction, translate_integrity_errors
from carteis.data.repositories.locations import LocationRepository
from carteis.domain.errors import NotFoundError
from carteis.domain.models import Invoice, Trip
from carteis.domain.pricing import Location

_SELECT_INVOICES = "SELECT id, client_dni, driver_id, issued_on FROM invoices"
_SELECT_TRIPS = """
    SELECT t.id, t.invoice_id, t.km, t.rate_cents,
           op.name AS origin_province, om.name AS origin_municipality,
           dp.name AS destination_province, dm.name AS destination_municipality
    FROM trips t
    JOIN municipalities om ON om.id = t.origin_id
    JOIN provinces op ON op.id = om.province_id
    JOIN municipalities dm ON dm.id = t.destination_id
    JOIN provinces dp ON dp.id = dm.province_id
"""
_DUPLICATE = "Ya existe una factura con ese número."


class InvoiceRepository:
    """Invoices are loaded and saved together with their trips."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._locations = LocationRepository(conn)

    def get(self, invoice_id: int) -> Invoice | None:
        row = self._conn.execute(_SELECT_INVOICES + " WHERE id = ?", (invoice_id,)).fetchone()
        if row is None:
            return None
        trips = self._conn.execute(
            _SELECT_TRIPS + " WHERE t.invoice_id = ? ORDER BY t.id", (invoice_id,)
        )
        return _to_invoice(row, [_to_trip(trip) for trip in trips])

    def list(self, client_dni: str | None = None) -> list[Invoice]:
        """All invoices (or one client's), newest number first, with their trips."""
        where, params = ("", ()) if client_dni is None else (" WHERE client_dni = ?", (client_dni,))
        rows = self._conn.execute(_SELECT_INVOICES + where + " ORDER BY id DESC", params).fetchall()

        trips_by_invoice: dict[int, list[Trip]] = defaultdict(list)
        trip_where = (
            ""
            if client_dni is None
            else (" WHERE t.invoice_id IN (SELECT id FROM invoices WHERE client_dni = ?)")
        )
        for trip in self._conn.execute(_SELECT_TRIPS + trip_where + " ORDER BY t.id", params):
            trips_by_invoice[trip["invoice_id"]].append(_to_trip(trip))

        return [_to_invoice(row, trips_by_invoice[row["id"]]) for row in rows]

    def add(self, invoice: Invoice) -> Invoice:
        """Insert the invoice and all its trips atomically (fixes bug D5)."""
        with transaction(self._conn), translate_integrity_errors(_DUPLICATE):
            cursor = self._conn.execute(
                "INSERT INTO invoices (id, client_dni, driver_id, issued_on) VALUES (?, ?, ?, ?)",
                (invoice.id, invoice.client_dni, invoice.driver_id, date_to_db(invoice.issued_on)),
            )
            invoice.id = cursor.lastrowid
            for trip in invoice.trips:
                self.add_trip(invoice.id, trip)
        return invoice

    def update(self, invoice: Invoice) -> None:
        """Update the invoice header (client, driver, date). Trips are edited one by one."""
        if invoice.id is None:
            raise ValueError("Cannot update an invoice that has not been saved")
        with translate_integrity_errors(_DUPLICATE):
            cursor = self._conn.execute(
                "UPDATE invoices SET client_dni = ?, driver_id = ?, issued_on = ? WHERE id = ?",
                (
                    invoice.client_dni,
                    invoice.driver_id,
                    date_to_db(invoice.issued_on),
                    invoice.id,
                ),
            )
        if cursor.rowcount == 0:
            raise NotFoundError("La factura no existe.")

    def delete(self, invoice_id: int) -> None:
        """Delete the invoice; its trips go with it through ON DELETE CASCADE."""
        cursor = self._conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        if cursor.rowcount == 0:
            raise NotFoundError("La factura no existe.")

    def add_trip(self, invoice_id: int, trip: Trip) -> Trip:
        with translate_integrity_errors("Ya existe ese viaje."):
            cursor = self._conn.execute(
                """
                INSERT INTO trips (id, invoice_id, origin_id, destination_id, km, rate_cents)
                VALUES (:id, :invoice_id, :origin_id, :destination_id, :km, :rate_cents)
                """,
                self._trip_values(trip) | {"invoice_id": invoice_id},
            )
        trip.id = cursor.lastrowid
        trip.invoice_id = invoice_id
        return trip

    def update_trip(self, trip: Trip) -> None:
        if trip.id is None:
            raise ValueError("Cannot update a trip that has not been saved")
        cursor = self._conn.execute(
            """
            UPDATE trips SET origin_id = :origin_id, destination_id = :destination_id,
                km = :km, rate_cents = :rate_cents
            WHERE id = :id
            """,
            self._trip_values(trip),
        )
        if cursor.rowcount == 0:
            raise NotFoundError("El viaje no existe.")

    def delete_trip(self, trip_id: int) -> None:
        cursor = self._conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        if cursor.rowcount == 0:
            raise NotFoundError("El viaje no existe.")

    def _trip_values(self, trip: Trip) -> dict:
        return {
            "id": trip.id,
            "origin_id": self._locations.municipality_id(trip.origin),
            "destination_id": self._locations.municipality_id(trip.destination),
            "km": trip.km,
            "rate_cents": money_to_cents(trip.rate),
        }


def _to_invoice(row: sqlite3.Row, trips: list[Trip]) -> Invoice:
    return Invoice(
        id=row["id"],
        client_dni=row["client_dni"],
        driver_id=row["driver_id"],
        issued_on=date_from_db(row["issued_on"]),
        trips=trips,
    )


def _to_trip(row: sqlite3.Row) -> Trip:
    return Trip(
        id=row["id"],
        invoice_id=row["invoice_id"],
        origin=Location(row["origin_province"], row["origin_municipality"]),
        destination=Location(row["destination_province"], row["destination_municipality"]),
        km=row["km"],
        rate=cents_to_money(row["rate_cents"]),
    )
