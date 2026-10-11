from datetime import date
from decimal import Decimal

import pytest

from carteis.domain.errors import InvalidStateError, ValidationError
from carteis.domain.models import Client, Driver, Invoice, License, Trip
from carteis.domain.pricing import Location

VIGO = Location("Pontevedra", "Vigo")
FERROL = Location("A Coruña", "Ferrol")
ALEGRIA = Location("Álava", "Alegría-Dulantzi")
ALATOZ = Location("Albacete", "Alatoz")


def make_driver(**overrides):
    fields = {
        "dni": "12345678z",
        "surname": " Gómez ",
        "name": "Ana",
        "address": "Avenida del Sol",
        "province": "Barcelona",
        "municipality": "Barcelona",
        "phone": "612345678",
        "salary": Decimal("35000"),
        "licenses": {"B"},
        "hired_on": date(2021, 9, 15),
    }
    return Driver(**(fields | overrides))


def make_client(**overrides):
    fields = {
        "dni": "53854586V",
        "company_name": "So Factive",
        "address": "Estrela",
        "province": "Pontevedra",
        "municipality": "Marín",
        "phone": "619669207",
    }
    return Client(**(fields | overrides))


class TestDriver:
    def test_normalizes_fields(self):
        driver = make_driver()
        assert driver.dni == "12345678Z"
        assert driver.surname == "Gómez"
        assert driver.licenses == frozenset({License.B})
        assert driver.is_active

    @pytest.mark.parametrize(
        "field, value",
        [
            ("dni", "12345678A"),
            ("surname", ""),
            ("name", "  "),
            ("address", ""),
            ("province", ""),
            ("municipality", ""),
            ("phone", "123"),
            ("salary", Decimal("-1")),
            ("licenses", set()),
            ("licenses", {"E"}),
        ],
    )
    def test_rejects_invalid_field(self, field, value):
        with pytest.raises(ValidationError) as error:
            make_driver(**{field: value})
        assert error.value.field == field

    def test_hire_date_is_optional_for_legacy_records(self):
        assert make_driver(hired_on=None).hired_on is None

    def test_rejects_leave_before_hire(self):
        with pytest.raises(ValidationError):
            make_driver(left_on=date(2020, 1, 1))

    def test_deactivate_keeps_hire_date(self):
        # Bug D3: the legacy code wiped the hire date when deactivating.
        driver = make_driver()
        driver.deactivate(date(2024, 1, 31))
        assert not driver.is_active
        assert driver.left_on == date(2024, 1, 31)
        assert driver.hired_on == date(2021, 9, 15)

    def test_cannot_deactivate_twice(self):
        driver = make_driver(left_on=date(2024, 1, 31))
        with pytest.raises(InvalidStateError, match="conductor ya está dado de baja"):
            driver.deactivate(date(2024, 2, 1))

    def test_cannot_deactivate_before_hire_date(self):
        with pytest.raises(ValidationError):
            make_driver().deactivate(date(2020, 1, 1))

    def test_reactivate(self):
        driver = make_driver(left_on=date(2024, 1, 31))
        driver.reactivate()
        assert driver.is_active

    def test_cannot_reactivate_active(self):
        with pytest.raises(InvalidStateError, match="ya está dado de alta"):
            make_driver().reactivate()


class TestClient:
    def test_valid_client(self):
        client = make_client(dni="x3381753v")
        assert client.dni == "X3381753V"
        assert client.is_active

    @pytest.mark.parametrize(
        "field, value",
        [
            ("dni", "nope"),
            ("company_name", ""),
            ("address", ""),
            ("province", ""),
            ("municipality", ""),
            ("phone", "12"),
        ],
    )
    def test_rejects_invalid_field(self, field, value):
        with pytest.raises(ValidationError):
            make_client(**{field: value})

    def test_deactivate_and_reactivate(self):
        client = make_client()
        client.deactivate(date(2024, 2, 20))
        assert not client.is_active
        with pytest.raises(InvalidStateError, match="cliente ya está dado de baja"):
            client.deactivate(date(2024, 2, 21))
        client.reactivate()
        assert client.is_active


class TestTrip:
    def test_amount(self):
        trip = Trip(origin=VIGO, destination=FERROL, km=12, rate=Decimal("0.80"))
        assert trip.amount == Decimal("9.60")
        assert trip.destination.province == "A Coruña"

    @pytest.mark.parametrize(
        "field, value", [("km", 0), ("km", -5), ("rate", Decimal("0")), ("rate", Decimal("-1"))]
    )
    def test_rejects_invalid_field(self, field, value):
        fields = {"origin": VIGO, "destination": VIGO, "km": 10, "rate": Decimal("0.20")}
        with pytest.raises(ValidationError) as error:
            Trip(**(fields | {field: value}))
        assert error.value.field == field


class TestInvoice:
    def test_totals_from_trips(self):
        invoice = Invoice(
            client_dni="71784575b",
            issued_on=date(2023, 12, 26),
            driver_id=13,
            trips=[
                Trip(origin=ALEGRIA, destination=ALATOZ, km=12, rate=Decimal("0.8")),
                Trip(origin=ALEGRIA, destination=ALEGRIA, km=10, rate=Decimal("0.2")),
            ],
        )
        assert invoice.client_dni == "71784575B"
        assert invoice.totals.subtotal == Decimal("11.60")
        assert invoice.totals.total == Decimal("14.04")

    def test_empty_invoice_totals_zero(self):
        invoice = Invoice(client_dni="71784575B", issued_on=date(2024, 1, 1), driver_id=1)
        assert invoice.totals.total == 0

    def test_rejects_bad_client_and_driver(self):
        with pytest.raises(ValidationError):
            Invoice(client_dni="bad", issued_on=date(2024, 1, 1), driver_id=1)
        with pytest.raises(ValidationError):
            Invoice(client_dni="71784575B", issued_on=date(2024, 1, 1), driver_id=0)
