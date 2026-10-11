"""Registering, editing and (de)activating drivers and clients."""

import sqlite3
from collections.abc import Callable
from datetime import date
from typing import Protocol

from carteis.data.repositories import ClientRepository, DriverRepository
from carteis.domain.errors import NotFoundError, ValidationError
from carteis.domain.models import Client, Driver
from carteis.domain.validators import validate_dni


class _Person(Protocol):
    id: int | None
    dni: str
    left_on: date | None

    @property
    def is_active(self) -> bool: ...
    def deactivate(self, on: date) -> None: ...
    def reactivate(self) -> None: ...


class _Repository[T](Protocol):
    def get(self, record_id: int) -> T | None: ...
    def get_by_dni(self, dni: str) -> T | None: ...
    def list(self, active: bool | None = None) -> list[T]: ...
    def add(self, record: T) -> T: ...
    def update(self, record: T) -> None: ...


class _PersonService[T: _Person]:
    _noun = "registro"  # used in messages: "No existe ningún {noun} ..."

    def __init__(self, repository: _Repository[T], today: Callable[[], date] = date.today):
        self._repo = repository
        self._today = today

    def get(self, record_id: int) -> T:
        record = self._repo.get(record_id)
        if record is None:
            raise NotFoundError(f"No existe ningún {self._noun} con el código {record_id}.")
        return record

    def find_by_dni(self, dni: str) -> T:
        """Fixes bug F1: an unknown DNI is reported instead of failing silently."""
        dni = validate_dni(dni)
        record = self._repo.get_by_dni(dni)
        if record is None:
            raise NotFoundError(f"No existe ningún {self._noun} con el DNI {dni}.")
        return record

    def list(self, active: bool | None = None) -> list[T]:
        return self._repo.list(active)

    def register(self, record: T) -> T:
        if not record.is_active:
            raise ValidationError("Un alta nueva no puede tener fecha de baja.", field="left_on")
        self._check_new(record)
        return self._repo.add(record)

    def update(self, record: T) -> bool:
        """Save changes. Returns ``False`` (and saves nothing) if nothing changed."""
        if record.id is None:
            raise ValidationError(f"Selecciona un {self._noun} para modificarlo.")
        if self.get(record.id) == record:
            return False
        self._repo.update(record)
        return True

    def deactivate(self, record_id: int, on: date | None = None) -> T:
        record = self.get(record_id)
        record.deactivate(on or self._today())
        self._repo.update(record)
        return record

    def reactivate(self, record_id: int) -> T:
        record = self.get(record_id)
        record.reactivate()
        self._repo.update(record)
        return record

    def _check_new(self, record: T) -> None:
        """Extra rules for new records; subclasses override it."""


class DriverService(_PersonService[Driver]):
    _noun = "conductor"

    def __init__(self, conn: sqlite3.Connection, today: Callable[[], date] = date.today):
        super().__init__(DriverRepository(conn), today)

    def _check_new(self, record: Driver) -> None:
        if record.hired_on is None:
            raise ValidationError("La fecha de alta es obligatoria.", field="hired_on")


class ClientService(_PersonService[Client]):
    _noun = "cliente"

    def __init__(self, conn: sqlite3.Connection, today: Callable[[], date] = date.today):
        super().__init__(ClientRepository(conn), today)
