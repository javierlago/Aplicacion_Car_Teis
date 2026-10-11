"""Creating invoices and editing their trips. Fares always come from the tariff."""

import sqlite3
from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal

from carteis.data.database import transaction
from carteis.data.repositories import ClientRepository, DriverRepository, InvoiceRepository
from carteis.domain.errors import InvalidStateError, NotFoundError, ValidationError
from carteis.domain.models import Invoice, Trip
from carteis.domain.pricing import FareType, Location, Tariff, fare_type
from carteis.domain.validators import validate_dni


class InvoicingService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        tariff: Tariff | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._conn = conn
        self._invoices = InvoiceRepository(conn)
        self._clients = ClientRepository(conn)
        self._drivers = DriverRepository(conn)
        self._tariff = tariff or Tariff()
        self._today = today

    def fare_for(self, origin: Location, destination: Location) -> tuple[FareType, Decimal]:
        """Fare type and price per km for a route (the UI shows both while typing)."""
        fare = fare_type(origin, destination)
        return fare, self._tariff.rate_for(fare)

    def new_trip(self, origin: Location, destination: Location, km: int) -> Trip:
        """Build an unsaved trip priced with the current tariff."""
        _, rate = self.fare_for(origin, destination)
        return Trip(origin=origin, destination=destination, km=km, rate=rate)

    def create_invoice(
        self,
        client_dni: str,
        driver_id: int,
        trips: Sequence[Trip],
        issued_on: date | None = None,
    ) -> Invoice:
        if not trips:
            raise ValidationError("Añade al menos un viaje para crear la factura.", field="trips")
        client = self._clients.get_by_dni(validate_dni(client_dni))
        if client is None:
            raise NotFoundError(f"No existe ningún cliente con el DNI {client_dni.strip()}.")
        if not client.is_active:
            raise InvalidStateError("No se puede facturar a un cliente dado de baja.")
        driver = self._drivers.get(driver_id)
        if driver is None:
            raise NotFoundError("El conductor seleccionado no existe.")
        if not driver.is_active:
            raise InvalidStateError("No se puede facturar con un conductor dado de baja.")

        invoice = Invoice(
            client_dni=client.dni,
            driver_id=driver.id,
            issued_on=issued_on or self._today(),
            trips=list(trips),
        )
        return self._invoices.add(invoice)

    def get(self, invoice_id: int) -> Invoice:
        invoice = self._invoices.get(invoice_id)
        if invoice is None:
            raise NotFoundError(f"No existe la factura número {invoice_id}.")
        return invoice

    def list(self, client_dni: str | None = None) -> list[Invoice]:
        return self._invoices.list(validate_dni(client_dni) if client_dni else None)

    def delete_invoice(self, invoice_id: int) -> None:
        self._invoices.delete(invoice_id)

    def add_trip(self, invoice_id: int, origin: Location, destination: Location, km: int) -> Trip:
        trip = self.new_trip(origin, destination, km)
        with transaction(self._conn):
            self.get(invoice_id)
            return self._invoices.add_trip(invoice_id, trip)

    def update_trip(
        self, invoice_id: int, trip_id: int, origin: Location, destination: Location, km: int
    ) -> bool:
        """Change a trip's route or distance and re-price it. ``False`` if nothing changed."""
        trip = self._find_trip(invoice_id, trip_id)
        updated = self.new_trip(origin, destination, km)
        if (trip.origin, trip.destination, trip.km) == (updated.origin, updated.destination, km):
            return False
        trip.origin, trip.destination, trip.km, trip.rate = (
            updated.origin,
            updated.destination,
            updated.km,
            updated.rate,
        )
        self._invoices.update_trip(trip)
        return True

    def delete_trip(self, invoice_id: int, trip_id: int) -> None:
        self._find_trip(invoice_id, trip_id)
        self._invoices.delete_trip(trip_id)

    def _find_trip(self, invoice_id: int, trip_id: int) -> Trip:
        for trip in self.get(invoice_id).trips:
            if trip.id == trip_id:
                return trip
        raise NotFoundError("El viaje no pertenece a esta factura.")
