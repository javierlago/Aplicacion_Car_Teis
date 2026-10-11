from decimal import Decimal

import pytest

from carteis.domain.errors import ValidationError
from carteis.domain.validators import (
    is_valid_dni,
    parse_money,
    require_text,
    validate_dni,
    validate_phone,
)


@pytest.mark.parametrize(
    "dni",
    ["12345678Z", "00000000T", "X1234567L", "Y1234567X", "Z1234567R", "X3381753V"],
)
def test_valid_dni_and_nie(dni):
    assert is_valid_dni(dni)


@pytest.mark.parametrize(
    "dni",
    [
        "12345678A",  # wrong letter
        "1234567Z",
        "123456789Z",
        "",
        "1234A678Z",
        "W1234567L",  # not a NIE prefix
        "X12345678L",  # NIE with 8 digits
        "12345678",  # no letter
        "12345678-Z",
    ],
)
def test_invalid_dni(dni):
    assert not is_valid_dni(dni)


def test_validate_dni_normalizes_case_and_spaces():
    assert validate_dni("  12345678z ") == "12345678Z"


def test_validate_dni_raises_with_field():
    with pytest.raises(ValidationError) as error:
        validate_dni("12345678A")
    assert error.value.field == "dni"


@pytest.mark.parametrize("phone", ["612345678", " 986123456 "])
def test_valid_phone(phone):
    assert validate_phone(phone) == phone.strip()


@pytest.mark.parametrize("phone", ["61234567", "6123456789", "61234567a", "", "612345678.0"])
def test_invalid_phone(phone):
    with pytest.raises(ValidationError):
        validate_phone(phone)


def test_require_text_strips_and_reports_label():
    assert require_text("  Vigo ", "Localidad") == "Vigo"
    with pytest.raises(ValidationError, match="«Localidad»"):
        require_text("   ", "Localidad", "municipality")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1500", "1500.00"),
        ("1500.5", "1500.50"),
        ("1500,5", "1500.50"),
        ("0", "0.00"),
        ("1.500", "1500.00"),  # Spanish thousands separator
        ("1.500.000", "1500000.00"),
        ("1.500,50", "1500.50"),
        # Formats stored in the legacy database
        ("30000,00 €", "30000.00"),
        ("28.000,00 €", "28000.00"),
        ("35000.0", "35000.00"),
        ("31000.00", "31000.00"),
        ("1.500,50 €", "1500.50"),
    ],
)
def test_parse_money(text, expected):
    assert parse_money(text) == Decimal(expected)


@pytest.mark.parametrize(
    "text", ["", "abc", "-10", "1500.505", "1,500,50", "1.500,505", "€", "12a"]
)
def test_parse_money_rejects(text):
    with pytest.raises(ValidationError):
        parse_money(text, field="salary")
