from datetime import date
from decimal import Decimal

import pytest

from carteis.services import ClientService, DriverService, InvoicingService
from tests.factories import FERROL, VIGO, make_client, make_driver
from tests.ui.conftest import TODAY, click_row, table_texts


@pytest.fixture
def data(conn, window):
    driver = DriverService(conn).register(make_driver())
    client = ClientService(conn).register(make_client())
    window.invoicing.reload_drivers()
    return driver, client


def set_route(ui, origin=("Pontevedra", "Vigo"), destination=("A Coruña", "Ferrol"), km="12"):
    ui.cmbTripOriginProvince.setCurrentText(origin[0])
    ui.cmbTripOriginMunicipality.setCurrentText(origin[1])
    ui.cmbTripDestinationProvince.setCurrentText(destination[0])
    ui.cmbTripDestinationMunicipality.setCurrentText(destination[1])
    ui.txtTripKm.setText(km)


def fill_header(ui, driver, client, issued="26/12/2023"):
    ui.txtInvoiceClientDni.setText(client.dni)
    ui.cmbInvoiceDriver.setCurrentIndex(ui.cmbInvoiceDriver.findData(driver.id))
    ui.txtInvoiceDate.setText(issued)


def test_driver_combo_lists_all_drivers(window, conn, data):
    driver, _ = data
    other = DriverService(conn).register(make_driver(dni="00000000T", surname="Abad"))
    DriverService(conn).deactivate(other.id)
    window.invoicing.reload_drivers()
    combo = window.ui.cmbInvoiceDriver
    items = [combo.itemText(i) for i in range(combo.count())]
    assert items == ["", f"{other.id} - Abad, Ana (baja)", f"{driver.id} - Gómez, Ana"]


def test_fare_follows_route(window, data):
    ui = window.ui
    assert not any(r.isChecked() for r in (ui.rbtFareLocal, ui.rbtFareNational))
    set_route(ui)
    assert ui.rbtFareNational.isChecked()
    set_route(ui, destination=("Pontevedra", "Cangas"))
    assert ui.rbtFareProvincial.isChecked()
    set_route(ui, destination=("Pontevedra", "Vigo"))
    assert ui.rbtFareLocal.isChecked()
    ui.cmbTripDestinationProvince.setCurrentIndex(0)
    assert not ui.rbtFareLocal.isChecked()


def test_vat_label_shows_rate(window):
    assert window.ui.lblVat.text() == "IVA (21%):"


def test_create_invoice(window, prompts, conn, data):
    driver, client = data
    ui = window.ui
    fill_header(ui, driver, client)
    set_route(ui)
    ui.btnInvoiceCreate.click()

    invoice = InvoicingService(conn).list()[0]
    assert prompts.last == ("info", f"Factura {invoice.id} creada.")
    assert invoice.issued_on == date(2023, 12, 26)
    assert ui.txtInvoiceNumber.text() == str(invoice.id)
    assert table_texts(ui.tblTrips, 1) == ["Vigo"]
    assert table_texts(ui.tblTrips, 5) == ["9,60 €"]
    assert (ui.txtSubtotal.text(), ui.txtVat.text(), ui.txtTotal.text()) == (
        "9,60 €",
        "2,02 €",
        "11,62 €",
    )
    assert ui.txtTripKm.text() == ""  # trip panel cleared for the next one


def test_create_invoice_defaults_to_today(window, conn, data):
    driver, client = data
    fill_header(window.ui, driver, client, issued="")
    set_route(window.ui)
    window.ui.btnInvoiceCreate.click()
    assert InvoicingService(conn).list()[0].issued_on == date.today()


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda ui: ui.cmbInvoiceDriver.setCurrentIndex(0), "Selecciona un conductor."),
        (lambda ui: ui.txtInvoiceClientDni.setText("bad"), "El DNI/NIE no es válido."),
        (lambda ui: ui.txtTripKm.setText("doce"), "El campo «Kms» debe ser un número entero."),
        (lambda ui: ui.txtTripKm.setText("0"), "Los kilómetros deben ser mayores que cero."),
        (
            lambda ui: ui.txtInvoiceClientDni.setText("00000000T"),
            "No existe ningún cliente con el DNI 00000000T.",
        ),
    ],
)
def test_create_invoice_errors(window, prompts, conn, data, change, message):
    driver, client = data
    ui = window.ui
    fill_header(ui, driver, client)
    set_route(ui)
    change(ui)
    ui.btnInvoiceCreate.click()
    assert prompts.last == ("warning", message)
    assert InvoicingService(conn).list() == []


def test_cannot_create_while_an_invoice_is_selected(window, prompts, conn, data):
    driver, client = data
    service = InvoicingService(conn)
    invoice = service.create_invoice(client.dni, driver.id, [service.new_trip(VIGO, VIGO, 1)])
    window.invoicing.refresh()
    click_row(window.ui.tblInvoices, 0)
    set_route(window.ui)
    window.ui.btnInvoiceCreate.click()
    kind, text = prompts.last
    assert kind == "warning" and f"La factura {invoice.id} está seleccionada" in text


@pytest.fixture
def invoice(conn, window, data):
    driver, client = data
    service = InvoicingService(conn)
    invoice = service.create_invoice(
        client.dni, driver.id, [service.new_trip(VIGO, FERROL, 12)], issued_on=date(2024, 1, 2)
    )
    window.invoicing.refresh()
    click_row(window.ui.tblInvoices, 0)
    return invoice


def test_select_invoice_shows_header_and_trips(window, invoice, data):
    driver, client = data
    ui = window.ui
    assert ui.txtInvoiceNumber.text() == str(invoice.id)
    assert ui.txtInvoiceClientDni.text() == client.dni
    assert ui.txtInvoiceDate.text() == "02/01/2024"
    assert ui.cmbInvoiceDriver.currentData() == driver.id
    assert table_texts(ui.tblTrips, 2) == ["Ferrol"]


def test_add_trip(window, conn, invoice):
    ui = window.ui
    set_route(ui, destination=("Pontevedra", "Vigo"), km="10")
    ui.btnTripSave.click()
    assert table_texts(ui.tblTrips, 4) == ["0,80 €", "0,20 €"]
    assert ui.txtTotal.text() == "14,04 €"
    assert len(InvoicingService(conn).get(invoice.id).trips) == 2


def test_add_trip_needs_an_invoice(window, prompts, data):
    set_route(window.ui)
    window.ui.btnTripSave.click()
    assert prompts.last == (
        "warning",
        "Selecciona una factura de la tabla, o crea una nueva con «Facturar».",
    )


def test_update_trip(window, prompts, conn, invoice):
    ui = window.ui
    assert ui.btnTripUpdate.isHidden()
    click_row(ui.tblTrips, 0)
    assert not ui.btnTripUpdate.isHidden()
    assert ui.cmbTripDestinationMunicipality.currentText() == "Ferrol"
    assert ui.txtTripKm.text() == "12"

    ui.btnTripUpdate.click()
    assert prompts.last == ("info", "No se han modificado los datos del viaje.")

    ui.cmbTripDestinationProvince.setCurrentText("Pontevedra")
    ui.cmbTripDestinationMunicipality.setCurrentText("Cangas")
    ui.btnTripUpdate.click()
    assert prompts.last == ("info", "Viaje modificado.")
    trip = InvoicingService(conn).get(invoice.id).trips[0]
    assert (trip.destination.municipality, trip.rate) == ("Cangas", Decimal("0.40"))
    assert ui.btnTripUpdate.isHidden()


def test_update_trip_needs_a_trip(window, prompts, invoice):
    window.invoicing._trip = None
    window.ui.btnTripUpdate.click()
    assert prompts.last == ("warning", "Selecciona un viaje de la tabla para modificarlo.")


def test_delete_trip_asks_first(window, prompts, conn, invoice):
    ui = window.ui
    button = ui.tblTrips.indexWidget(ui.tblTrips.model().index(0, 6))
    prompts.confirm_answers.append(False)
    button.click()
    assert len(InvoicingService(conn).get(invoice.id).trips) == 1
    click_row(ui.tblTrips, 0)
    ui.tblTrips.indexWidget(ui.tblTrips.model().index(0, 6)).click()
    assert prompts.last == ("confirm", "¿Eliminar este viaje?")
    assert InvoicingService(conn).get(invoice.id).trips == []
    assert ui.txtTotal.text() == "0,00 €"


def test_delete_invoice(window, prompts, conn, invoice):
    ui = window.ui
    delete = ui.tblInvoices.indexWidget(ui.tblInvoices.model().index(0, 2))
    prompts.confirm_answers.append(False)
    delete.click()
    assert len(InvoicingService(conn).list()) == 1
    ui.tblInvoices.indexWidget(ui.tblInvoices.model().index(0, 2)).click()
    assert prompts.last == ("confirm", f"¿Eliminar la factura {invoice.id} y todos sus viajes?")
    assert InvoicingService(conn).list() == []
    assert ui.txtInvoiceNumber.text() == ""


def test_filter_by_client(window, prompts, conn, invoice, data):
    driver, _ = data
    other = ClientService(conn).register(make_client(dni="00000000T", company_name="Otra"))
    ui = window.ui
    ui.btnInvoiceClear.click()
    assert ui.txtInvoiceNumber.text() == ""
    ui.txtInvoiceClientDni.setText(other.dni)
    ui.btnInvoiceClientSearch.click()
    assert prompts.last == ("info", "Otra no tiene facturas.")
    assert table_texts(ui.tblInvoices, 0) == []
    ui.btnInvoiceClear.click()
    assert table_texts(ui.tblInvoices, 0) == [str(invoice.id)]


def test_invoice_date_calendar(window, prompts):
    prompts.dates.append(TODAY)
    window.ui.btnInvoiceDateCalendar.click()
    assert window.ui.txtInvoiceDate.text() == "11/10/2026"
    window.ui.btnInvoiceDateCalendar.click()
    assert prompts.calendar_opened_on[-1] == TODAY


def test_delete_errors_are_shown_not_raised(window, prompts, conn, invoice):
    """A trip or invoice deleted behind the screen's back is reported as a warning."""
    ui = window.ui
    stale_trip = ui.tblTrips.indexWidget(ui.tblTrips.model().index(0, 6))
    stale_invoice = ui.tblInvoices.indexWidget(ui.tblInvoices.model().index(0, 2))
    InvoicingService(conn).delete_invoice(invoice.id)
    stale_trip.click()
    assert prompts.last == ("warning", f"No existe la factura número {invoice.id}.")
    stale_invoice.click()
    assert prompts.last == ("warning", "La factura no existe.")
