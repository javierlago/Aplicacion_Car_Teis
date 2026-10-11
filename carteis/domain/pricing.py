"""Fares and invoice totals. All money is ``Decimal`` rounded to cents (half up)."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from carteis import config
from carteis.domain.money import to_cents
from carteis.domain.validators import require_text


class FareType(StrEnum):
    LOCAL = "local"  # same municipality
    PROVINCIAL = "provincial"  # same province, different municipality
    NATIONAL = "national"  # different province


@dataclass(frozen=True)
class Location:
    province: str
    municipality: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "province", require_text(self.province, "Provincia"))
        object.__setattr__(self, "municipality", require_text(self.municipality, "Localidad"))


def fare_type(origin: Location, destination: Location) -> FareType:
    if origin.province.casefold() != destination.province.casefold():
        return FareType.NATIONAL
    if origin.municipality.casefold() != destination.municipality.casefold():
        return FareType.PROVINCIAL
    return FareType.LOCAL


@dataclass(frozen=True)
class Tariff:
    """Price per kilometre for each fare type."""

    local: Decimal = config.LOCAL_RATE
    provincial: Decimal = config.PROVINCIAL_RATE
    national: Decimal = config.NATIONAL_RATE

    def rate_for(self, fare: FareType) -> Decimal:
        return {
            FareType.LOCAL: self.local,
            FareType.PROVINCIAL: self.provincial,
            FareType.NATIONAL: self.national,
        }[fare]

    def rate_between(self, origin: Location, destination: Location) -> Decimal:
        return self.rate_for(fare_type(origin, destination))


def line_amount(km: int, rate: Decimal) -> Decimal:
    return to_cents(Decimal(km) * rate)


@dataclass(frozen=True)
class InvoiceTotals:
    subtotal: Decimal
    vat: Decimal
    total: Decimal


def compute_totals(
    amounts: Iterable[Decimal], vat_rate: Decimal = config.VAT_RATE
) -> InvoiceTotals:
    """Sum the (already rounded) line amounts, then add VAT rounded to cents."""
    subtotal = to_cents(sum(amounts, Decimal("0")))
    vat = to_cents(subtotal * vat_rate)
    return InvoiceTotals(subtotal=subtotal, vat=vat, total=subtotal + vat)
