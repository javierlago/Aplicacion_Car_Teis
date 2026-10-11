import contextlib
import sqlite3
from collections.abc import Callable

from PyQt6.QtWidgets import QLineEdit

from carteis.data.repositories import LocationRepository
from carteis.domain.errors import ValidationError
from carteis.domain.formatting import format_date
from carteis.domain.models import Driver, License
from carteis.domain.validators import parse_money
from carteis.services import DriverService
from carteis.ui.forms import (
    LocationPicker,
    read_money,
    read_optional_date,
    show_dni_check,
    try_read_date,
    user_action,
    write_date,
    write_money,
)
from carteis.ui.generated.main_window import Ui_MainWindow
from carteis.ui.prompts import Prompts
from carteis.ui.table_models import Column, attach_model, select_row

COLUMNS = [
    Column[Driver]("Código", lambda d: d.id),
    Column[Driver]("Apellidos", lambda d: d.surname, stretch=True),
    Column[Driver]("Nombre", lambda d: d.name, stretch=True),
    Column[Driver]("Móvil", lambda d: d.phone),
    Column[Driver]("Licencias", lambda d: "-".join(sorted(d.licenses))),
    Column[Driver]("Fecha baja", lambda d: format_date(d.left_on)),
]


class DriversTab:
    def __init__(
        self,
        ui: Ui_MainWindow,
        conn: sqlite3.Connection,
        prompts: Prompts,
        on_change: Callable[[], None] = lambda: None,
    ) -> None:
        self.ui = ui
        self.prompts = prompts
        self._service = DriverService(conn)
        self._on_change = on_change  # e.g. reload the driver list in the invoicing tab
        self._selected: Driver | None = None
        self._location = LocationPicker(
            LocationRepository(conn), ui.cmbDriverProvince, ui.cmbDriverMunicipality
        )
        self._model = attach_model(ui.tblDrivers, COLUMNS)
        self._licenses = {
            License.A: ui.chkLicenseA,
            License.B: ui.chkLicenseB,
            License.C: ui.chkLicenseC,
            License.D: ui.chkLicenseD,
        }
        self.field_widgets = {
            "dni": ui.txtDriverDni,
            "surname": ui.txtDriverSurname,
            "name": ui.txtDriverName,
            "address": ui.txtDriverAddress,
            "province": ui.cmbDriverProvince,
            "municipality": ui.cmbDriverMunicipality,
            "phone": ui.txtDriverPhone,
            "salary": ui.txtDriverSalary,
            "licenses": ui.chkLicenseA,
            "hired_on": ui.txtDriverHiredOn,
            "left_on": ui.txtDriverLeftOn,
        }

        ui.grpDriverStatus.buttonClicked.connect(lambda _button: self.refresh())
        ui.tblDrivers.clicked.connect(self._on_row_clicked)
        ui.btnDriverRegister.clicked.connect(self._register)
        ui.btnDriverUpdate.clicked.connect(self._update)
        ui.btnDriverDeactivate.clicked.connect(self._toggle_active)
        ui.btnDriverSearch.clicked.connect(self._search)
        ui.btnDriverHiredOnCalendar.clicked.connect(lambda: self._pick_date(ui.txtDriverHiredOn))
        ui.btnDriverLeftOnCalendar.clicked.connect(lambda: self._pick_date(ui.txtDriverLeftOn))
        ui.txtDriverDni.textChanged.connect(lambda text: show_dni_check(ui.lblDriverDniCheck, text))
        for edit in (ui.txtDriverSurname, ui.txtDriverName):
            edit.editingFinished.connect(lambda edit=edit: edit.setText(edit.text().title()))
        ui.txtDriverSalary.editingFinished.connect(self._format_salary)
        self.clear()

    # ---- list ------------------------------------------------------------------------

    def _status_filter(self) -> bool | None:
        if self.ui.rbtDriversActive.isChecked():
            return True
        if self.ui.rbtDriversInactive.isChecked():
            return False
        return None

    def refresh(self) -> None:
        self._model.set_records(self._service.list(self._status_filter()))
        selected_id = self._selected.id if self._selected else None
        select_row(self.ui.tblDrivers, self._model.row_where(lambda d: d.id == selected_id))
        self._update_state_widgets()

    def _show_status(self, driver: Driver) -> None:
        """Switch the status filter so ``driver`` is listed."""
        if self._status_filter() not in (None, driver.is_active):
            radio = self.ui.rbtDriversActive if driver.is_active else self.ui.rbtDriversInactive
            radio.setChecked(True)

    def _on_row_clicked(self, index) -> None:
        self._load(self._model.record(index.row()))

    # ---- form ------------------------------------------------------------------------

    def _load(self, driver: Driver) -> None:
        self._selected = driver
        ui = self.ui
        ui.lblDriverIdValue.setText(str(driver.id))
        ui.txtDriverDni.setText(driver.dni)
        ui.txtDriverSurname.setText(driver.surname)
        ui.txtDriverName.setText(driver.name)
        ui.txtDriverAddress.setText(driver.address)
        self._location.set_location(driver.province, driver.municipality)
        ui.txtDriverPhone.setText(driver.phone)
        write_money(ui.txtDriverSalary, driver.salary)
        for license_type, checkbox in self._licenses.items():
            checkbox.setChecked(license_type in driver.licenses)
        write_date(ui.txtDriverHiredOn, driver.hired_on)
        write_date(ui.txtDriverLeftOn, driver.left_on)
        self._show_status(driver)
        self.refresh()

    def _read_form(self) -> Driver:
        ui = self.ui
        location = self._location.location()
        return Driver(
            id=self._selected.id if self._selected else None,
            dni=ui.txtDriverDni.text(),
            surname=ui.txtDriverSurname.text(),
            name=ui.txtDriverName.text(),
            address=ui.txtDriverAddress.text(),
            province=location.province,
            municipality=location.municipality,
            phone=ui.txtDriverPhone.text(),
            salary=read_money(ui.txtDriverSalary, "salary", "Salario"),
            licenses=frozenset(lic for lic, box in self._licenses.items() if box.isChecked()),
            hired_on=read_optional_date(ui.txtDriverHiredOn, "hired_on"),
            left_on=read_optional_date(ui.txtDriverLeftOn, "left_on"),
        )

    def clear(self) -> None:
        self._selected = None
        ui = self.ui
        ui.lblDriverIdValue.clear()
        for edit in (
            ui.txtDriverDni,
            ui.txtDriverSurname,
            ui.txtDriverName,
            ui.txtDriverAddress,
            ui.txtDriverPhone,
            ui.txtDriverSalary,
            ui.txtDriverHiredOn,
            ui.txtDriverLeftOn,
        ):
            edit.clear()
        self._location.clear()
        for checkbox in self._licenses.values():
            checkbox.setChecked(False)
        self.refresh()

    def _update_state_widgets(self) -> None:
        inactive = self._selected is not None and not self._selected.is_active
        self.ui.btnDriverDeactivate.setText("Reactivar" if inactive else "Baja")
        self.ui.driverLeftOnFrame.setVisible(inactive or self._status_filter() is False)

    def _pick_date(self, edit: QLineEdit) -> None:
        picked = self.prompts.pick_date(try_read_date(edit))
        if picked:
            write_date(edit, picked)

    def _format_salary(self) -> None:
        with contextlib.suppress(ValidationError):  # reported when the form is saved
            write_money(self.ui.txtDriverSalary, parse_money(self.ui.txtDriverSalary.text()))

    def _require_selection(self, verb: str) -> Driver:
        if self._selected is None:
            raise ValidationError(f"Selecciona un conductor de la tabla para {verb}.")
        return self._selected

    # ---- actions ---------------------------------------------------------------------

    @user_action
    def _register(self) -> None:
        driver = self._read_form()
        driver.id = None
        self._service.register(driver)
        self.prompts.info(f"Conductor {driver.name} {driver.surname} dado de alta.")
        self._selected = driver
        self._show_status(driver)
        self.refresh()
        self._on_change()

    @user_action
    def _update(self) -> None:
        self._require_selection("modificarlo")
        driver = self._read_form()
        if not self._service.update(driver):
            self.prompts.info("No se han modificado los datos.")
            return
        self._selected = driver
        self.prompts.info("Datos del conductor modificados.")
        self._show_status(driver)
        self.refresh()
        self._on_change()

    @user_action
    def _toggle_active(self) -> None:
        selected = self._require_selection("darlo de baja")
        if selected.is_active:
            left_on = read_optional_date(self.ui.txtDriverLeftOn, "left_on")
            driver = self._service.deactivate(selected.id, left_on)
            self.prompts.info("Conductor dado de baja.")
        else:
            driver = self._service.reactivate(selected.id)
            self.prompts.info("Conductor dado de alta de nuevo.")
        self._load(driver)
        self._on_change()

    @user_action
    def _search(self) -> None:
        self._load(self._service.find_by_dni(self.ui.txtDriverDni.text()))
