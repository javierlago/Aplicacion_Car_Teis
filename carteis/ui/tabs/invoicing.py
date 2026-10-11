import sqlite3

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QRadioButton

from carteis import config
from carteis.data.repositories import LocationRepository
from carteis.domain.errors import ValidationError
from carteis.domain.formatting import format_money
from carteis.domain.models import Invoice, Trip
from carteis.domain.pricing import FareType
from carteis.domain.validators import validate_dni
from carteis.services import ClientService, DriverService, InvoicingService
from carteis.ui.forms import (
    LocationPicker,
    read_int,
    read_optional_date,
    try_read_date,
    user_action,
    write_date,
)
from carteis.ui.generated.main_window import Ui_MainWindow
from carteis.ui.prompts import Prompts
from carteis.ui.table_models import Column, add_row_buttons, attach_model, select_row

INVOICE_COLUMNS = [
    Column[Invoice]("Factura", lambda i: i.id),
    Column[Invoice]("Cliente", lambda i: i.client_dni, stretch=True),
    Column[Invoice]("", lambda i: None),  # delete button
]
TRIP_COLUMNS = [
    Column[Trip]("Viaje", lambda t: t.id),
    Column[Trip]("Origen", lambda t: t.origin.municipality, stretch=True),
    Column[Trip]("Destino", lambda t: t.destination.municipality, stretch=True),
    Column[Trip]("Km", lambda t: t.km),
    Column[Trip]("Tarifa", lambda t: format_money(t.rate)),
    Column[Trip]("Total", lambda t: format_money(t.amount)),
    Column[Trip]("", lambda t: None),  # delete button
]
_DELETE_INVOICE_COLUMN = len(INVOICE_COLUMNS) - 1
_DELETE_TRIP_COLUMN = len(TRIP_COLUMNS) - 1


class InvoicingTab:
    def __init__(self, ui: Ui_MainWindow, conn: sqlite3.Connection, prompts: Prompts) -> None:
        self.ui = ui
        self.prompts = prompts
        self._service = InvoicingService(conn)
        self._drivers = DriverService(conn)
        self._clients = ClientService(conn)
        self._invoice: Invoice | None = None
        self._trip: Trip | None = None
        self._client_filter: str | None = None

        locations = LocationRepository(conn)
        self._origin = LocationPicker(
            locations, ui.cmbTripOriginProvince, ui.cmbTripOriginMunicipality
        )
        self._destination = LocationPicker(
            locations, ui.cmbTripDestinationProvince, ui.cmbTripDestinationMunicipality
        )
        self._invoices = attach_model(ui.tblInvoices, INVOICE_COLUMNS)
        self._trips = attach_model(ui.tblTrips, TRIP_COLUMNS)
        self._fare_radios: dict[FareType, QRadioButton] = {
            FareType.LOCAL: ui.rbtFareLocal,
            FareType.PROVINCIAL: ui.rbtFareProvincial,
            FareType.NATIONAL: ui.rbtFareNational,
        }
        for radio in self._fare_radios.values():  # they show the fare, the user can't pick it
            radio.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            radio.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        ui.txtInvoiceNumber.setReadOnly(True)
        for total in (ui.txtSubtotal, ui.txtVat, ui.txtTotal):
            total.setReadOnly(True)
        ui.lblVat.setText(f"IVA ({(config.VAT_RATE * 100).normalize():f}%):")
        self.field_widgets = {
            "dni": ui.txtInvoiceClientDni,
            "driver_id": ui.cmbInvoiceDriver,
            "issued_on": ui.txtInvoiceDate,
            "province": ui.cmbTripOriginProvince,
            "municipality": ui.cmbTripOriginMunicipality,
            "km": ui.txtTripKm,
        }

        ui.tblInvoices.clicked.connect(
            lambda index: self._select_invoice(self._invoices.record(index.row()))
        )
        ui.tblTrips.clicked.connect(
            lambda index: self._select_trip(self._trips.record(index.row()))
        )
        ui.btnInvoiceCreate.clicked.connect(self._create_invoice)
        ui.btnInvoiceClear.clicked.connect(self.clear)
        ui.btnInvoiceClientSearch.clicked.connect(self._filter_by_client)
        ui.btnInvoiceDateCalendar.clicked.connect(self._pick_date)
        ui.btnTripSave.clicked.connect(self._add_trip)
        ui.btnTripUpdate.clicked.connect(self._update_trip)
        ui.btnTripClear.clicked.connect(self._clear_trip_panel)
        for combo in (ui.cmbTripOriginMunicipality, ui.cmbTripDestinationMunicipality):
            combo.currentTextChanged.connect(lambda _text: self._show_fare())

        self.reload_drivers()
        self.clear()

    @property
    def selected_invoice(self) -> Invoice | None:
        return self._invoice

    # ---- invoices --------------------------------------------------------------------

    def reload_drivers(self) -> None:
        """Fill the driver combo; inactive drivers stay listed so old invoices show them."""
        combo = self.ui.cmbInvoiceDriver
        current = combo.currentData()
        combo.clear()
        combo.addItem("", None)
        for driver in self._drivers.list():
            suffix = "" if driver.is_active else " (baja)"
            combo.addItem(f"{driver.id} - {driver.surname}, {driver.name}{suffix}", driver.id)
        self._select_driver(current)

    def _select_driver(self, driver_id: int | None) -> None:
        index = self.ui.cmbInvoiceDriver.findData(driver_id)
        self.ui.cmbInvoiceDriver.setCurrentIndex(max(index, 0))

    def refresh(self) -> None:
        invoices = self._service.list(self._client_filter)
        self._invoices.set_records(invoices)
        add_row_buttons(
            self.ui.tblInvoices, self._invoices, _DELETE_INVOICE_COLUMN, self._delete_invoice
        )
        if self._invoice is not None:
            self._invoice = next((i for i in invoices if i.id == self._invoice.id), None)
        current_id = self._invoice.id if self._invoice else None
        select_row(self.ui.tblInvoices, self._invoices.row_where(lambda i: i.id == current_id))
        self._show_invoice()

    def _show_invoice(self) -> None:
        ui, invoice = self.ui, self._invoice
        ui.txtInvoiceNumber.setText(str(invoice.id) if invoice else "")
        if invoice:
            ui.txtInvoiceClientDni.setText(invoice.client_dni)
            write_date(ui.txtInvoiceDate, invoice.issued_on)
            self._select_driver(invoice.driver_id)
        trips = invoice.trips if invoice else []
        self._trips.set_records(trips)
        add_row_buttons(ui.tblTrips, self._trips, _DELETE_TRIP_COLUMN, self._delete_trip)
        current_id = self._trip.id if self._trip else None
        select_row(ui.tblTrips, self._trips.row_where(lambda t: t.id == current_id))
        totals = invoice.totals if invoice else None
        for edit, value in (
            (ui.txtSubtotal, totals and totals.subtotal),
            (ui.txtVat, totals and totals.vat),
            (ui.txtTotal, totals and totals.total),
        ):
            edit.setText(format_money(value) if totals else "")

    def _select_invoice(self, invoice: Invoice) -> None:
        self._invoice = invoice
        self._clear_trip_panel()

    def clear(self) -> None:
        """Forget the selected invoice and the client filter; empty both panels."""
        self._invoice = None
        self._client_filter = None
        self.ui.txtInvoiceClientDni.clear()
        self.ui.txtInvoiceDate.clear()
        self._select_driver(None)
        self._clear_trip_panel()

    def _pick_date(self) -> None:
        picked = self.prompts.pick_date(try_read_date(self.ui.txtInvoiceDate))
        if picked:
            write_date(self.ui.txtInvoiceDate, picked)

    @user_action
    def _filter_by_client(self) -> None:
        client = self._clients.find_by_dni(self.ui.txtInvoiceClientDni.text())
        self._client_filter = client.dni
        self._invoice = None
        self.refresh()
        if not self._invoices.rowCount():
            self.prompts.info(f"{client.company_name} no tiene facturas.")

    @user_action
    def _create_invoice(self) -> None:
        if self._invoice is not None:
            raise ValidationError(
                f"La factura {self._invoice.id} está seleccionada. Pulsa limpiar para crear una "
                "nueva, o «Grabar» para añadirle un viaje."
            )
        driver_id = self.ui.cmbInvoiceDriver.currentData()
        if driver_id is None:
            raise ValidationError("Selecciona un conductor.", field="driver_id")
        client_dni = validate_dni(self.ui.txtInvoiceClientDni.text())
        issued_on = read_optional_date(self.ui.txtInvoiceDate, "issued_on")
        invoice = self._service.create_invoice(
            client_dni, driver_id, [self._trip_from_panel()], issued_on
        )
        self.prompts.info(f"Factura {invoice.id} creada.")
        self._invoice = invoice
        self._clear_trip_panel()

    def _delete_invoice(self, invoice: Invoice) -> None:
        if not self.prompts.confirm(f"¿Eliminar la factura {invoice.id} y todos sus viajes?"):
            return
        self._service.delete_invoice(invoice.id)
        if self._invoice and self._invoice.id == invoice.id:
            self._invoice = None
        self.refresh()

    # ---- trips -----------------------------------------------------------------------

    def _trip_from_panel(self) -> Trip:
        return self._service.new_trip(
            self._origin.location(),
            self._destination.location(),
            read_int(self.ui.txtTripKm, "km", "Kms"),
        )

    def _show_fare(self) -> None:
        group = self.ui.grpFare
        group.setExclusive(False)
        for radio in self._fare_radios.values():
            radio.setChecked(False)
        group.setExclusive(True)
        try:
            fare, _ = self._service.fare_for(self._origin.location(), self._destination.location())
        except ValidationError:
            return  # route not complete yet
        self._fare_radios[fare].setChecked(True)

    def _select_trip(self, trip: Trip) -> None:
        self._trip = trip
        self._origin.set_location(trip.origin.province, trip.origin.municipality)
        self._destination.set_location(trip.destination.province, trip.destination.municipality)
        self.ui.txtTripKm.setText(str(trip.km))
        self.ui.btnTripUpdate.setVisible(True)
        self.refresh()

    def _clear_trip_panel(self) -> None:
        self._trip = None
        self._origin.clear()
        self._destination.clear()
        self.ui.txtTripKm.clear()
        self.ui.btnTripUpdate.setVisible(False)
        self.refresh()

    def _require_invoice(self) -> Invoice:
        if self._invoice is None:
            raise ValidationError(
                "Selecciona una factura de la tabla, o crea una nueva con «Facturar»."
            )
        return self._invoice

    @user_action
    def _add_trip(self) -> None:
        invoice = self._require_invoice()
        trip = self._trip_from_panel()
        self._service.add_trip(invoice.id, trip.origin, trip.destination, trip.km)
        self._clear_trip_panel()

    @user_action
    def _update_trip(self) -> None:
        invoice = self._require_invoice()
        if self._trip is None:
            raise ValidationError("Selecciona un viaje de la tabla para modificarlo.")
        trip = self._trip_from_panel()
        if not self._service.update_trip(
            invoice.id, self._trip.id, trip.origin, trip.destination, trip.km
        ):
            self.prompts.info("No se han modificado los datos del viaje.")
            return
        self.prompts.info("Viaje modificado.")
        self._clear_trip_panel()

    def _delete_trip(self, trip: Trip) -> None:
        if not self.prompts.confirm("¿Eliminar este viaje?"):
            return
        self._service.delete_trip(trip.invoice_id, trip.id)
        if self._trip and self._trip.id == trip.id:
            self._trip = None
        self.refresh()
