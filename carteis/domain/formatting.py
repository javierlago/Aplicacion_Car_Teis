"""Spanish display formats for dates and money.

Done by hand instead of through ``locale`` so the app no longer crashes when ``es_ES.UTF-8``
is not installed.
"""

from datetime import date, datetime
from decimal import Decimal

from carteis.domain.errors import ValidationError
from carteis.domain.money import to_cents

_DISPLAY_DATE_FORMAT = "%d/%m/%Y"


def format_date(value: date | None) -> str:
    return value.strftime(_DISPLAY_DATE_FORMAT) if value else ""


def parse_date(value: str, field: str | None = None) -> date:
    """Parse ``dd/mm/YYYY`` (how the UI and legacy data write dates) or ISO ``YYYY-MM-DD``."""
    text = value.strip()
    for fmt in (_DISPLAY_DATE_FORMAT, "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValidationError(f"Fecha no válida: «{value}». Usa el formato dd/mm/aaaa.", field=field)


def format_money(value: Decimal) -> str:
    """``Decimal("1500.5")`` → ``"1.500,50 €"``."""
    amount = to_cents(value)
    sign = "-" if amount < 0 else ""
    integer, cents = f"{abs(amount):.2f}".split(".")
    grouped = f"{int(integer):,}".replace(",", ".")
    return f"{sign}{grouped},{cents} €"
