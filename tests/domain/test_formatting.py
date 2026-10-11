from datetime import date
from decimal import Decimal

import pytest

from carteis.domain.errors import ValidationError
from carteis.domain.formatting import format_date, format_money, parse_date


def test_format_date():
    assert format_date(date(2024, 2, 5)) == "05/02/2024"
    assert format_date(None) == ""


@pytest.mark.parametrize("text", ["05/02/2024", "2024-02-05", " 05/02/2024 "])
def test_parse_date_accepts_display_and_iso(text):
    assert parse_date(text) == date(2024, 2, 5)


@pytest.mark.parametrize("text", ["", "31/02/2024", "2024/02/05", "5-2-2024", "hoy"])
def test_parse_date_rejects(text):
    with pytest.raises(ValidationError):
        parse_date(text, field="hired_on")


@pytest.mark.parametrize(
    "value, expected",
    [
        ("0", "0,00 €"),
        ("5", "5,00 €"),
        ("1500.5", "1.500,50 €"),
        ("1234567.891", "1.234.567,89 €"),
        ("0.005", "0,01 €"),  # half up
        ("-12.5", "-12,50 €"),
    ],
)
def test_format_money(value, expected):
    assert format_money(Decimal(value)) == expected
