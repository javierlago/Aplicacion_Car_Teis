from decimal import Decimal

import pytest

from carteis.domain.errors import ValidationError
from carteis.domain.pricing import (
    FareType,
    Location,
    Tariff,
    compute_totals,
    fare_type,
    line_amount,
)

VIGO = Location("Pontevedra", "Vigo")
CANGAS = Location("Pontevedra", "Cangas")
FERROL = Location("A Coruña", "Ferrol")


@pytest.mark.parametrize(
    "origin, destination, expected",
    [
        (VIGO, VIGO, FareType.LOCAL),
        (VIGO, CANGAS, FareType.PROVINCIAL),
        (VIGO, FERROL, FareType.NATIONAL),
        (VIGO, Location("A Coruña", "Vigo"), FareType.NATIONAL),  # province wins
        (VIGO, Location(" pontevedra ", "VIGO"), FareType.LOCAL),  # case and spaces ignored
    ],
)
def test_fare_type(origin, destination, expected):
    assert fare_type(origin, destination) == expected


def test_location_requires_both_fields():
    with pytest.raises(ValidationError):
        Location("", "Vigo")
    with pytest.raises(ValidationError):
        Location("Pontevedra", "  ")


def test_default_tariff_matches_legacy_rates():
    tariff = Tariff()
    assert tariff.rate_for(FareType.LOCAL) == Decimal("0.20")
    assert tariff.rate_for(FareType.PROVINCIAL) == Decimal("0.40")
    assert tariff.rate_for(FareType.NATIONAL) == Decimal("0.80")


def test_custom_tariff():
    tariff = Tariff(local=Decimal("1"), provincial=Decimal("2"), national=Decimal("3"))
    assert tariff.rate_between(VIGO, CANGAS) == Decimal("2")


@pytest.mark.parametrize(
    "km, rate, expected",
    [(10, "0.20", "2.00"), (12, "0.80", "9.60"), (7, "0.333", "2.33"), (5, "0.001", "0.01")],
)
def test_line_amount(km, rate, expected):
    assert line_amount(km, Decimal(rate)) == Decimal(expected)


def test_totals_are_exact():
    # With floats 0.1 + 0.2 != 0.3 (see tests/legacy/test_pricing.py).
    totals = compute_totals([Decimal("0.10"), Decimal("0.20")])
    assert totals.subtotal == Decimal("0.30")


def test_totals_add_vat():
    totals = compute_totals([Decimal("9.60"), Decimal("2.00")])
    assert totals.subtotal == Decimal("11.60")
    assert totals.vat == Decimal("2.44")  # 2.436 rounded half up
    assert totals.total == Decimal("14.04")


def test_totals_of_no_lines():
    totals = compute_totals([])
    assert (totals.subtotal, totals.vat, totals.total) == (0, 0, 0)


def test_custom_vat_rate():
    assert compute_totals([Decimal("100")], vat_rate=Decimal("0.10")).total == Decimal("110.00")
