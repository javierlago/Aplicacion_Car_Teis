import sqlite3

from PyQt6.QtWidgets import QLineEdit

from carteis.data.repositories import LocationRepository
from carteis.domain.errors import ValidationError
from carteis.domain.models import Client
from carteis.services import ClientService
from carteis.ui.forms import (
    LocationPicker,
    read_optional_date,
    show_dni_check,
    try_read_date,
    user_action,
    write_date,
)
from carteis.ui.generated.main_window import Ui_MainWindow
from carteis.ui.prompts import Prompts
from carteis.ui.table_models import Column, attach_model, select_row

COLUMNS = [
    Column[Client]("Código", lambda c: c.id),
    Column[Client]("Razón social", lambda c: c.company_name, stretch=True),
    Column[Client]("Teléfono", lambda c: c.phone),
    Column[Client]("Provincia", lambda c: c.province, stretch=True),
]


class ClientsTab:
    def __init__(self, ui: Ui_MainWindow, conn: sqlite3.Connection, prompts: Prompts) -> None:
        self.ui = ui
        self.prompts = prompts
        self._service = ClientService(conn)
        self._selected: Client | None = None
        self._location = LocationPicker(
            LocationRepository(conn), ui.cmbClientProvince, ui.cmbClientMunicipality
        )
        self._model = attach_model(ui.tblClients, COLUMNS)
        self.field_widgets = {
            "dni": ui.txtClientDni,
            "company_name": ui.txtClientCompanyName,
            "address": ui.txtClientAddress,
            "province": ui.cmbClientProvince,
            "municipality": ui.cmbClientMunicipality,
            "phone": ui.txtClientPhone,
            "left_on": ui.txtClientLeftOn,
        }

        ui.grpClientStatus.buttonClicked.connect(lambda _button: self.refresh())
        ui.tblClients.clicked.connect(lambda index: self._load(self._model.record(index.row())))
        ui.btnClientRegister.clicked.connect(self._register)
        ui.btnClientUpdate.clicked.connect(self._update)
        ui.btnClientDeactivate.clicked.connect(self._toggle_active)
        ui.btnClientSearch.clicked.connect(self._search)
        ui.btnClientLeftOnCalendar.clicked.connect(lambda: self._pick_date(ui.txtClientLeftOn))
        ui.txtClientDni.textChanged.connect(lambda text: show_dni_check(ui.lblClientDniCheck, text))
        self.clear()

    def _status_filter(self) -> bool | None:
        if self.ui.rbtClientsActive.isChecked():
            return True
        if self.ui.rbtClientsInactive.isChecked():
            return False
        return None

    def refresh(self) -> None:
        self._model.set_records(self._service.list(self._status_filter()))
        selected_id = self._selected.id if self._selected else None
        select_row(self.ui.tblClients, self._model.row_where(lambda c: c.id == selected_id))
        inactive = self._selected is not None and not self._selected.is_active
        self.ui.btnClientDeactivate.setText("Reactivar" if inactive else "Baja")
        self.ui.clientLeftOnFrame.setVisible(inactive or self._status_filter() is False)

    def _show_status(self, client: Client) -> None:
        if self._status_filter() not in (None, client.is_active):
            radio = self.ui.rbtClientsActive if client.is_active else self.ui.rbtClientsInactive
            radio.setChecked(True)

    def _load(self, client: Client) -> None:
        self._selected = client
        ui = self.ui
        ui.lblClientIdValue.setText(str(client.id))
        ui.txtClientDni.setText(client.dni)
        ui.txtClientCompanyName.setText(client.company_name)
        ui.txtClientAddress.setText(client.address)
        self._location.set_location(client.province, client.municipality)
        ui.txtClientPhone.setText(client.phone)
        write_date(ui.txtClientLeftOn, client.left_on)
        self._show_status(client)
        self.refresh()

    def _read_form(self) -> Client:
        ui = self.ui
        location = self._location.location()
        return Client(
            id=self._selected.id if self._selected else None,
            dni=ui.txtClientDni.text(),
            company_name=ui.txtClientCompanyName.text(),
            address=ui.txtClientAddress.text(),
            province=location.province,
            municipality=location.municipality,
            phone=ui.txtClientPhone.text(),
            left_on=read_optional_date(ui.txtClientLeftOn, "left_on"),
        )

    def clear(self) -> None:
        self._selected = None
        ui = self.ui
        ui.lblClientIdValue.clear()
        for edit in (
            ui.txtClientDni,
            ui.txtClientCompanyName,
            ui.txtClientAddress,
            ui.txtClientPhone,
            ui.txtClientLeftOn,
        ):
            edit.clear()
        self._location.clear()
        self.refresh()

    def _pick_date(self, edit: QLineEdit) -> None:
        picked = self.prompts.pick_date(try_read_date(edit))
        if picked:
            write_date(edit, picked)

    def _require_selection(self, verb: str) -> Client:
        if self._selected is None:
            raise ValidationError(f"Selecciona un cliente de la tabla para {verb}.")
        return self._selected

    @user_action
    def _register(self) -> None:
        client = self._read_form()
        client.id = None
        self._service.register(client)
        self.prompts.info(f"Cliente {client.company_name} dado de alta.")
        self._selected = client
        self._show_status(client)
        self.refresh()

    @user_action
    def _update(self) -> None:
        self._require_selection("modificarlo")
        client = self._read_form()
        if not self._service.update(client):
            self.prompts.info("No se han modificado los datos.")
            return
        self._selected = client
        self.prompts.info("Datos del cliente modificados.")
        self._show_status(client)
        self.refresh()

    @user_action
    def _toggle_active(self) -> None:
        selected = self._require_selection("darlo de baja")
        if selected.is_active:
            left_on = read_optional_date(self.ui.txtClientLeftOn, "left_on")
            client = self._service.deactivate(selected.id, left_on)
            self.prompts.info("Cliente dado de baja.")
        else:
            client = self._service.reactivate(selected.id)
            self.prompts.info("Cliente dado de alta de nuevo.")
        self._load(client)

    @user_action
    def _search(self) -> None:
        self._load(self._service.find_by_dni(self.ui.txtClientDni.text()))
