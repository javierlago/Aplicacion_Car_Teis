"""Helpers shared by the tab controllers."""

import functools
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Protocol

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QComboBox, QLabel, QLineEdit, QWidget

from carteis.data.repositories import LocationRepository
from carteis.domain.errors import DomainError, ValidationError
from carteis.domain.formatting import format_date, format_money, parse_date
from carteis.domain.pricing import Location
from carteis.domain.validators import is_valid_dni, parse_money
from carteis.ui.prompts import Prompts


class _Controller(Protocol):
    prompts: Prompts
    field_widgets: dict[str, QWidget]


def user_action[C: _Controller](method: Callable[[C], None]) -> Callable[..., None]:
    """Wrap a slot: show any ``DomainError`` to the user and focus the offending field.

    Signal arguments (e.g. ``clicked(bool)``) are ignored.
    """

    @functools.wraps(method)
    def slot(self: C, *_signal_args) -> None:
        try:
            method(self)
        except DomainError as error:
            self.prompts.warning(str(error))
            field = getattr(error, "field", None)
            if field in self.field_widgets:
                self.field_widgets[field].setFocus()

    return slot


def fill_combo(combo: QComboBox, items: list[str]) -> None:
    """Replace the items, keeping a blank first entry (nothing selected)."""
    combo.blockSignals(True)
    combo.clear()
    combo.addItem("")
    combo.addItems(items)
    combo.blockSignals(False)


class LocationPicker:
    """A province combo that fills its municipality combo."""

    def __init__(
        self, locations: LocationRepository, province: QComboBox, municipality: QComboBox
    ) -> None:
        self._locations = locations
        self.province = province
        self.municipality = municipality
        fill_combo(province, locations.provinces())
        fill_combo(municipality, [])
        province.currentTextChanged.connect(self._load_municipalities)

    def _load_municipalities(self, province: str) -> None:
        fill_combo(self.municipality, self._locations.municipalities(province) if province else [])
        # fill_combo blocks signals; announce the (now empty) selection once.
        self.municipality.currentTextChanged.emit(self.municipality.currentText())

    def location(self) -> Location:
        return Location(self.province.currentText(), self.municipality.currentText())

    def set_location(self, province: str, municipality: str) -> None:
        self.province.setCurrentText(province)  # reloads municipalities synchronously
        self.municipality.setCurrentText(municipality)

    def clear(self) -> None:
        self.province.setCurrentIndex(0)


def read_optional_date(edit: QLineEdit, field: str) -> date | None:
    text = edit.text().strip()
    return parse_date(text, field=field) if text else None


def try_read_date(edit: QLineEdit) -> date | None:
    """The date in ``edit``, or ``None`` if it is empty or not a valid date."""
    try:
        return read_optional_date(edit, "")
    except ValidationError:
        return None


def write_date(edit: QLineEdit, value: date | None) -> None:
    edit.setText(format_date(value))


def read_money(edit: QLineEdit, field: str, label: str) -> Decimal:
    if not edit.text().strip():
        raise ValidationError(f"El campo «{label}» es obligatorio.", field=field)
    return parse_money(edit.text(), field=field)


def write_money(edit: QLineEdit, value: Decimal | None) -> None:
    edit.setText(format_money(value) if value is not None else "")


def read_int(edit: QLineEdit, field: str, label: str) -> int:
    text = edit.text().strip()
    if not text.isdigit():
        raise ValidationError(f"El campo «{label}» debe ser un número entero.", field=field)
    return int(text)


def show_dni_check(label: QLabel, dni: str) -> None:
    """Tick or cross next to a DNI box; nothing while it is empty."""
    if not dni.strip():
        label.clear()
        return
    label.setScaledContents(True)
    label.setPixmap(QPixmap("img:OkIco.svg" if is_valid_dni(dni) else "img:CancelIco.ico"))
