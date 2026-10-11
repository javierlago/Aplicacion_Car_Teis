from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def to_cents(value: Decimal) -> Decimal:
    """Round to two decimals, half up (how amounts are rounded on invoices)."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)
