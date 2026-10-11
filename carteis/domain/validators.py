"""Field validation. Each function returns the normalized value or raises ``ValidationError``."""

import re
from decimal import Decimal

from carteis.domain.errors import ValidationError
from carteis.domain.money import CENT

_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIE_PREFIX_DIGIT = {"X": "0", "Y": "1", "Z": "2"}
_DNI_PATTERN = re.compile(r"([XYZ]\d{7}|\d{8})([A-Z])")
_PHONE_PATTERN = re.compile(r"\d{9}")
_THOUSANDS_ONLY_PATTERN = re.compile(r"\d{1,3}(\.\d{3})+")
_AMOUNT_PATTERN = re.compile(r"\d+(\.\d{1,2})?")


def normalize_dni(value: str) -> str:
    return value.strip().upper()


def is_valid_dni(value: str) -> bool:
    """Check a Spanish DNI (8 digits + letter) or NIE (X/Y/Z + 7 digits + letter)."""
    match = _DNI_PATTERN.fullmatch(normalize_dni(value))
    if not match:
        return False
    number, letter = match.groups()
    if number[0] in _NIE_PREFIX_DIGIT:
        number = _NIE_PREFIX_DIGIT[number[0]] + number[1:]
    return _DNI_LETTERS[int(number) % 23] == letter


def validate_dni(value: str) -> str:
    if not is_valid_dni(value):
        raise ValidationError("El DNI/NIE no es válido.", field="dni")
    return normalize_dni(value)


def validate_phone(value: str) -> str:
    phone = value.strip()
    if not _PHONE_PATTERN.fullmatch(phone):
        raise ValidationError("El teléfono debe tener 9 dígitos.", field="phone")
    return phone


def require_text(value: str, label: str, field: str | None = None) -> str:
    """Return ``value`` stripped, or raise if blank. ``label`` is the name shown to the user."""
    text = value.strip()
    if not text:
        raise ValidationError(f"El campo «{label}» es obligatorio.", field=field)
    return text


def parse_money(value: str, field: str | None = None) -> Decimal:
    """Parse a non-negative amount with at most two decimals.

    Accepts the formats found in the legacy data and typed by users: ``1500``, ``1500.5``,
    ``1500,50``, ``1.500``, ``1.500,50`` and ``1.500,50 €``. Spanish convention: when both
    separators appear, ``.`` groups thousands and ``,`` is the decimal mark; a lone ``.`` followed
    by groups of exactly three digits (``1.500``) is also read as a thousands separator.
    """
    text = value.replace("€", "").replace(" ", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    elif _THOUSANDS_ONLY_PATTERN.fullmatch(text):
        text = text.replace(".", "")

    if not _AMOUNT_PATTERN.fullmatch(text):
        raise ValidationError(
            "Importe no válido: usa solo números y como máximo dos decimales.", field=field
        )
    return Decimal(text).quantize(CENT)
