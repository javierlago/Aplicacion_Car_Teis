from datetime import date
from decimal import Decimal

import pytest

from carteis.domain.errors import InvalidStateError, NotFoundError, ValidationError
from carteis.domain.pricing import FareType, Tariff
from carteis.services import ClientService, DriverService, InvoicingService
from tests.factories import CANGAS, FERROL, VIGO, make_client, make_driver

TODAY = date(2026, 10, 11)


@pytest.fixture
def setup(conn):
    driver = DriverService(conn).register(make_driver())
    client = ClientService(conn).register(make_client())
    service = InvoicingService(conn, today=lambda: TODAY)
    return service, driver, client


def test_fare_for_route(setup):
    service, _, _ = setup
    assert service.fare_for(VIGO, VIGO) == (FareType.LOCAL, Decimal("0.20"))
    assert service.fare_for(VIGO, CANGAS) == (FareType.PROVINCIAL, Decimal("0.40"))
    assert service.fare_for(VIGO, FERROL) == (FareType.NATIONAL, Decimal("0.80"))


def test_new_trip_uses_tariff(conn):
    service = InvoicingService(conn, tariff=Tariff(national=Decimal("1.10")))
    trip = service.new_trip(VIGO, FERROL, 10)
    assert trip.rate == Decimal("1.10")
    assert trip.amount == Decimal("11.00")
    assert trip.id is None


def test_create_invoice(setup):
    service, driver, client = setup
    invoice = service.create_invoice(
        client_dni=client.dni.lower(),
        driver_id=driver.id,
        trips=[service.new_trip(VIGO, FERROL, 12), service.new_trip(VIGO, VIGO, 10)],
    )
    stored = service.get(invoice.id)
    assert stored.issued_on == TODAY
    assert stored.client_dni == client.dni
    assert stored.totals.subtotal == Decimal("11.60")
    assert stored.totals.total == Decimal("14.04")
    assert service.list() == [stored]
    assert service.list(client_dni=client.dni) == [stored]


def test_create_invoice_with_date(setup):
    service, driver, client = setup
    invoice = service.create_invoice(
        client.dni, driver.id, [service.new_trip(VIGO, VIGO, 1)], issued_on=date(2024, 1, 2)
    )
    assert service.get(invoice.id).issued_on == date(2024, 1, 2)


def test_create_invoice_requires_trips(setup):
    service, driver, client = setup
    with pytest.raises(ValidationError, match="al menos un viaje"):
        service.create_invoice(client.dni, driver.id, [])


def test_create_invoice_client_checks(conn, setup):
    service, driver, client = setup
    trips = [service.new_trip(VIGO, VIGO, 1)]
    with pytest.raises(NotFoundError, match="ningún cliente"):
        service.create_invoice("00000000T", driver.id, trips)
    with pytest.raises(ValidationError):
        service.create_invoice("bad", driver.id, trips)
    ClientService(conn).deactivate(client.id)
    with pytest.raises(InvalidStateError, match="cliente dado de baja"):
        service.create_invoice(client.dni, driver.id, trips)
    assert service.list() == []


def test_create_invoice_driver_checks(conn, setup):
    service, driver, client = setup
    trips = [service.new_trip(VIGO, VIGO, 1)]
    with pytest.raises(NotFoundError, match="conductor"):
        service.create_invoice(client.dni, 999, trips)
    DriverService(conn).deactivate(driver.id)
    with pytest.raises(InvalidStateError, match="conductor dado de baja"):
        service.create_invoice(client.dni, driver.id, trips)


def test_get_and_delete(setup):
    service, driver, client = setup
    invoice = service.create_invoice(client.dni, driver.id, [service.new_trip(VIGO, VIGO, 1)])
    service.delete_invoice(invoice.id)
    with pytest.raises(NotFoundError, match=f"factura número {invoice.id}"):
        service.get(invoice.id)
    with pytest.raises(NotFoundError):
        service.delete_invoice(invoice.id)


def test_trip_editing(setup):
    service, driver, client = setup
    invoice = service.create_invoice(client.dni, driver.id, [service.new_trip(VIGO, VIGO, 10)])

    added = service.add_trip(invoice.id, VIGO, FERROL, 5)
    assert added.rate == Decimal("0.80")
    assert len(service.get(invoice.id).trips) == 2

    assert service.update_trip(invoice.id, added.id, VIGO, FERROL, 5) is False
    assert service.update_trip(invoice.id, added.id, VIGO, CANGAS, 7) is True
    updated = service.get(invoice.id).trips[1]
    assert (updated.destination, updated.km, updated.rate) == (CANGAS, 7, Decimal("0.40"))

    service.delete_trip(invoice.id, added.id)
    assert [t.km for t in service.get(invoice.id).trips] == [10]


def test_trip_must_belong_to_invoice(setup):
    service, driver, client = setup
    first = service.create_invoice(client.dni, driver.id, [service.new_trip(VIGO, VIGO, 1)])
    second = service.create_invoice(client.dni, driver.id, [service.new_trip(VIGO, VIGO, 2)])
    foreign_trip = second.trips[0].id
    with pytest.raises(NotFoundError, match="no pertenece"):
        service.delete_trip(first.id, foreign_trip)
    with pytest.raises(NotFoundError):
        service.update_trip(first.id, foreign_trip, VIGO, VIGO, 3)
    with pytest.raises(NotFoundError):
        service.add_trip(999, VIGO, VIGO, 3)
