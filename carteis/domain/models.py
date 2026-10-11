"""Domain entities. Each one validates and normalizes its fields on construction."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar

from carteis.domain.errors import InvalidStateError, ValidationError
from carteis.domain.pricing import InvoiceTotals, compute_totals, line_amount
from carteis.domain.validators import require_text, validate_dni, validate_phone


class License(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass(kw_only=True)
class _Deactivatable:
    """Soft delete: a record is active while it has no leave date."""

    _label: ClassVar[str] = "El registro"

    left_on: date | None = None

    @property
    def is_active(self) -> bool:
        return self.left_on is None

    def deactivate(self, on: date) -> None:
        if not self.is_active:
            raise InvalidStateError(f"{self._label} ya está dado de baja.")
        self.left_on = on

    def reactivate(self) -> None:
        if self.is_active:
            raise InvalidStateError(f"{self._label} ya está dado de alta.")
        self.left_on = None


@dataclass(kw_only=True)
class Driver(_Deactivatable):
    _label: ClassVar[str] = "El conductor"

    dni: str
    surname: str
    name: str
    address: str
    province: str
    municipality: str
    phone: str
    salary: Decimal
    licenses: frozenset[License]
    # Optional only because legacy data lost it for drivers who were deactivated (bug D3).
    hired_on: date | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        self.dni = validate_dni(self.dni)
        self.surname = require_text(self.surname, "Apellidos", "surname")
        self.name = require_text(self.name, "Nombre", "name")
        self.address = require_text(self.address, "Dirección", "address")
        self.province = require_text(self.province, "Provincia", "province")
        self.municipality = require_text(self.municipality, "Localidad", "municipality")
        self.phone = validate_phone(self.phone)
        if self.salary < 0:
            raise ValidationError("El salario no puede ser negativo.", field="salary")
        try:
            self.licenses = frozenset(License(item) for item in self.licenses)
        except ValueError as error:
            raise ValidationError("Tipo de carné no válido.", field="licenses") from error
        if not self.licenses:
            raise ValidationError("Selecciona al menos un tipo de carné.", field="licenses")
        self._check_dates(self.left_on)

    def deactivate(self, on: date) -> None:
        self._check_dates(on)
        super().deactivate(on)

    def _check_dates(self, left_on: date | None) -> None:
        if self.hired_on and left_on and left_on < self.hired_on:
            raise ValidationError(
                "La fecha de baja no puede ser anterior a la de alta.", field="left_on"
            )


@dataclass(kw_only=True)
class Client(_Deactivatable):
    _label: ClassVar[str] = "El cliente"

    dni: str
    company_name: str
    address: str
    province: str
    municipality: str
    phone: str
    id: int | None = None

    def __post_init__(self) -> None:
        self.dni = validate_dni(self.dni)
        self.company_name = require_text(self.company_name, "Razón social", "company_name")
        self.address = require_text(self.address, "Dirección", "address")
        self.province = require_text(self.province, "Provincia", "province")
        self.municipality = require_text(self.municipality, "Localidad", "municipality")
        self.phone = validate_phone(self.phone)


@dataclass(kw_only=True)
class Trip:
    """One invoice line. ``origin`` and ``destination`` are municipality names."""

    origin: str
    destination: str
    km: int
    rate: Decimal
    id: int | None = None
    invoice_id: int | None = None

    def __post_init__(self) -> None:
        self.origin = require_text(self.origin, "Origen", "origin")
        self.destination = require_text(self.destination, "Destino", "destination")
        if self.km <= 0:
            raise ValidationError("Los kilómetros deben ser mayores que cero.", field="km")
        if self.rate <= 0:
            raise ValidationError("La tarifa debe ser mayor que cero.", field="rate")

    @property
    def amount(self) -> Decimal:
        return line_amount(self.km, self.rate)


@dataclass(kw_only=True)
class Invoice:
    client_dni: str
    issued_on: date
    driver_id: int
    trips: list[Trip] = field(default_factory=list)
    id: int | None = None

    def __post_init__(self) -> None:
        self.client_dni = validate_dni(self.client_dni)
        if self.driver_id <= 0:
            raise ValidationError("Selecciona un conductor.", field="driver_id")

    @property
    def totals(self) -> InvoiceTotals:
        return compute_totals(trip.amount for trip in self.trips)
