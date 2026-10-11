from datetime import date
from decimal import Decimal

import pytest

from carteis.data.repositories import (
    ClientRepository,
    DriverRepository,
    InvoiceRepository,
    LocationRepository,
)
from carteis.domain.errors import DuplicateError, NotFoundError, ValidationError
from carteis.domain.models import Invoice, License, Trip
from carteis.domain.pricing import Location
from tests.factories import CANGAS, FERROL, VIGO, make_client, make_driver


class TestLocations:
    def test_lists(self, conn):
        repo = LocationRepository(conn)
        assert repo.provinces() == ["Pontevedra", "A Coruña", "Navarra", "Zaragoza"]
        assert repo.municipalities("Pontevedra") == ["Vigo", "Cangas"]
        assert repo.municipalities("Nowhere") == []

    def test_provinces_of_repeated_name(self, conn):
        assert LocationRepository(conn).provinces_of("Castejón") == ["Navarra", "Zaragoza"]

    def test_municipality_id(self, conn):
        repo = LocationRepository(conn)
        assert repo.municipality_id(Location("Zaragoza", "Castejón")) == 5
        with pytest.raises(ValidationError, match="no existe en la provincia"):
            repo.municipality_id(Location("A Coruña", "Vigo"))


class TestDrivers:
    def test_add_and_get_round_trip(self, conn):
        repo = DriverRepository(conn)
        driver = repo.add(make_driver())
        assert driver.id is not None
        assert repo.get(driver.id) == driver
        assert repo.get_by_dni(" 12345678z ") == driver
        assert repo.get(999) is None
        assert repo.get_by_dni("00000000T") is None

    def test_stored_formats(self, conn):
        DriverRepository(conn).add(make_driver())
        row = conn.execute(
            "SELECT salary_cents, licenses, hired_on, left_on FROM drivers"
        ).fetchone()
        assert tuple(row) == (150050, "A,B", "2021-09-15", None)

    def test_duplicate_dni(self, conn):
        repo = DriverRepository(conn)
        repo.add(make_driver())
        with pytest.raises(DuplicateError, match="conductor"):
            repo.add(make_driver(name="Otra"))

    def test_unknown_location(self, conn):
        with pytest.raises(ValidationError):
            DriverRepository(conn).add(make_driver(municipality="Ferrol"))

    def test_update_keeps_hire_date_on_deactivation(self, conn):
        repo = DriverRepository(conn)
        driver = repo.add(make_driver())
        driver.deactivate(date(2024, 1, 31))
        driver.licenses = frozenset({License.C})
        repo.update(driver)
        stored = repo.get(driver.id)
        assert stored.left_on == date(2024, 1, 31)
        assert stored.hired_on == date(2021, 9, 15)
        assert stored.licenses == {License.C}

    def test_update_errors(self, conn):
        repo = DriverRepository(conn)
        with pytest.raises(ValueError):
            repo.update(make_driver())
        with pytest.raises(NotFoundError):
            repo.update(make_driver(id=999))
        repo.add(make_driver())
        other = repo.add(make_driver(dni="00000000T"))
        other.dni = "12345678Z"
        with pytest.raises(DuplicateError):
            repo.update(other)

    def test_list_filters_and_orders(self, conn):
        repo = DriverRepository(conn)
        repo.add(make_driver(dni="12345678Z", surname="Zapata"))
        repo.add(make_driver(dni="00000000T", surname="Abad", left_on=date(2024, 1, 1)))
        repo.add(make_driver(dni="X1234567L", surname="López"))
        assert [d.surname for d in repo.list()] == ["Abad", "López", "Zapata"]
        assert [d.surname for d in repo.list(active=True)] == ["López", "Zapata"]
        assert [d.surname for d in repo.list(active=False)] == ["Abad"]

    def test_explicit_id_is_kept(self, conn):
        assert DriverRepository(conn).add(make_driver(id=42)).id == 42


class TestClients:
    def test_add_get_update(self, conn):
        repo = ClientRepository(conn)
        client = repo.add(make_client())
        assert repo.get(client.id) == client
        assert repo.get_by_dni("53854586v") == client
        client.address = "Nova 2"
        client.deactivate(date(2024, 2, 20))
        repo.update(client)
        assert repo.get(client.id).address == "Nova 2"
        assert repo.list(active=False) == [client]
        assert repo.list(active=True) == []
        assert repo.get(999) is None

    def test_errors(self, conn):
        repo = ClientRepository(conn)
        repo.add(make_client())
        with pytest.raises(DuplicateError, match="cliente"):
            repo.add(make_client())
        with pytest.raises(ValueError):
            repo.update(make_client())
        with pytest.raises(NotFoundError):
            repo.update(make_client(id=999))

    def test_list_orders_by_company_name(self, conn):
        repo = ClientRepository(conn)
        repo.add(make_client(dni="53854586V", company_name="Zeta"))
        repo.add(make_client(dni="12345678Z", company_name="Alfa"))
        assert [c.company_name for c in repo.list()] == ["Alfa", "Zeta"]


@pytest.fixture
def invoice_setup(conn):
    driver = DriverRepository(conn).add(make_driver())
    client = ClientRepository(conn).add(make_client())
    return conn, driver, client


def _trip(origin=VIGO, destination=FERROL, km=12, rate="0.80"):
    return Trip(origin=origin, destination=destination, km=km, rate=Decimal(rate))


class TestInvoices:
    def test_add_with_trips_round_trip(self, invoice_setup):
        conn, driver, client = invoice_setup
        repo = InvoiceRepository(conn)
        invoice = repo.add(
            Invoice(
                client_dni=client.dni,
                driver_id=driver.id,
                issued_on=date(2024, 2, 27),
                trips=[_trip(), _trip(destination=CANGAS, km=10, rate="0.40")],
            )
        )
        stored = repo.get(invoice.id)
        assert stored == invoice
        assert [t.invoice_id for t in stored.trips] == [invoice.id, invoice.id]
        assert stored.totals.subtotal == Decimal("13.60")
        assert repo.get(999) is None

    def test_add_is_atomic(self, invoice_setup):
        # Bug D5: an invoice could be saved without its trips.
        conn, driver, client = invoice_setup
        repo = InvoiceRepository(conn)
        bad_trip = _trip(destination=Location("A Coruña", "Vigo"))
        with pytest.raises(ValidationError):
            repo.add(
                Invoice(
                    client_dni=client.dni,
                    driver_id=driver.id,
                    issued_on=date(2024, 2, 27),
                    trips=[_trip(), bad_trip],
                )
            )
        assert repo.list() == []
        assert conn.execute("SELECT count(*) FROM trips").fetchone()[0] == 0

    def test_unknown_client_or_driver(self, invoice_setup):
        conn, driver, client = invoice_setup
        repo = InvoiceRepository(conn)
        with pytest.raises(NotFoundError):
            repo.add(Invoice(client_dni="00000000T", driver_id=driver.id, issued_on=date.today()))
        with pytest.raises(NotFoundError):
            repo.add(Invoice(client_dni=client.dni, driver_id=999, issued_on=date.today()))

    def test_duplicate_number(self, invoice_setup):
        conn, driver, client = invoice_setup
        repo = InvoiceRepository(conn)
        header = {"client_dni": client.dni, "driver_id": driver.id, "issued_on": date.today()}
        repo.add(Invoice(id=7, **header))
        with pytest.raises(DuplicateError):
            repo.add(Invoice(id=7, **header))

    def test_delete_cascades_to_trips(self, invoice_setup):
        # Bug D4: trips were left behind when their invoice was deleted.
        conn, driver, client = invoice_setup
        repo = InvoiceRepository(conn)
        invoice = repo.add(
            Invoice(
                client_dni=client.dni, driver_id=driver.id, issued_on=date.today(), trips=[_trip()]
            )
        )
        repo.delete(invoice.id)
        assert repo.get(invoice.id) is None
        assert conn.execute("SELECT count(*) FROM trips").fetchone()[0] == 0
        with pytest.raises(NotFoundError):
            repo.delete(invoice.id)

    def test_trip_operations(self, invoice_setup):
        conn, driver, client = invoice_setup
        repo = InvoiceRepository(conn)
        invoice = repo.add(
            Invoice(client_dni=client.dni, driver_id=driver.id, issued_on=date.today())
        )
        trip = repo.add_trip(invoice.id, _trip())
        trip.km = 20
        trip.destination = CANGAS
        repo.update_trip(trip)
        assert repo.get(invoice.id).trips == [trip]

        repo.delete_trip(trip.id)
        assert repo.get(invoice.id).trips == []
        with pytest.raises(NotFoundError):
            repo.delete_trip(trip.id)
        with pytest.raises(NotFoundError):
            repo.update_trip(trip)
        with pytest.raises(ValueError):
            repo.update_trip(_trip())

    def test_update_header(self, invoice_setup):
        conn, driver, client = invoice_setup
        repo = InvoiceRepository(conn)
        invoice = repo.add(
            Invoice(client_dni=client.dni, driver_id=driver.id, issued_on=date(2024, 1, 1))
        )
        invoice.issued_on = date(2024, 3, 1)
        repo.update(invoice)
        assert repo.get(invoice.id).issued_on == date(2024, 3, 1)
        with pytest.raises(ValueError):
            repo.update(Invoice(client_dni=client.dni, driver_id=driver.id, issued_on=date.today()))
        with pytest.raises(NotFoundError):
            repo.update(
                Invoice(id=999, client_dni=client.dni, driver_id=driver.id, issued_on=date.today())
            )

    def test_list_all_and_by_client(self, invoice_setup):
        conn, driver, client = invoice_setup
        other = ClientRepository(conn).add(make_client(dni="00000000T"))
        repo = InvoiceRepository(conn)
        first = repo.add(
            Invoice(
                client_dni=client.dni, driver_id=driver.id, issued_on=date.today(), trips=[_trip()]
            )
        )
        second = repo.add(
            Invoice(
                client_dni=other.dni,
                driver_id=driver.id,
                issued_on=date.today(),
                trips=[_trip(), _trip(km=5)],
            )
        )
        assert repo.list() == [second, first]  # newest first
        assert repo.list(client_dni=client.dni) == [first]
        assert len(repo.list(client_dni=other.dni)[0].trips) == 2
        assert repo.list(client_dni="12345678Z") == []
