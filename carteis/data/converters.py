"""Conversions between domain values and their SQLite storage format.

Dates are ISO ``YYYY-MM-DD`` text; money is an integer number of cents.
"""

from datetime import date
from decimal import Decimal

from carteis.domain.money import CENT


def date_to_db(value: date | None) -> str | None:
    return value.isoformat() if value else None


def date_from_db(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def money_to_cents(value: Decimal) -> int:
    cents = value / CENT
    if cents != cents.to_integral_value():
        raise ValueError(f"{value} has more than two decimals and cannot be stored exactly")
    return int(cents)


def cents_to_money(value: int) -> Decimal:
    return (Decimal(value) * CENT).quantize(CENT)
