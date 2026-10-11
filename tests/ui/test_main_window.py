from datetime import date

import pytest
from openpyxl import Workbook
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication

from carteis.services import ClientService, DriverService, InvoicingService
from carteis.ui.main_window import status_date
from tests.factories import VIGO, make_client, make_driver
from tests.ui.conftest import click_row, table_texts


def test_status_bar(window):
    labels = [w.text() for w in window.ui.statusbar.findChildren(type(window._status_date))]
    assert "domingo-11-10-2026" in labels
    assert "Versión: 0.0.0.1" in labels
    assert status_date(date(2024, 1, 1)) == "lunes-01-01-2024"


def test_list_reports(window, prompts, conn):
    DriverService(conn).register(make_driver())
    window.ui.actionReportDrivers.trigger()
    window.ui.actionReportClients.trigger()
    names = [path.name for path in prompts.opened]
    assert names[0].endswith("_listadoconductores.pdf")
    assert names[1].endswith("_listadoclientes.pdf")
    assert all(path.is_file() for path in prompts.opened)


def test_invoice_report_needs_a_selected_invoice(window, prompts, conn):
    window.ui.actionReportInvoice.trigger()
    assert prompts.last == (
        "warning",
        "Selecciona una factura en la pestaña Facturación para imprimirla.",
    )
    driver = DriverService(conn).register(make_driver())
    client = ClientService(conn).register(make_client())
    service = InvoicingService(conn)
    invoice = service.create_invoice(client.dni, driver.id, [service.new_trip(VIGO, VIGO, 1)])
    window.invoicing.refresh()
    click_row(window.ui.tblInvoices, 0)
    window.ui.actionReportInvoice.trigger()
    assert prompts.opened[-1].name.endswith(f"_factura_{invoice.id}.pdf")


def test_print_button_asks_which_reports(window, prompts):
    window.ui.actionPrintReports.trigger()  # cancelled
    assert prompts.opened == []
    assert prompts.offered == ["Listado de conductores", "Listado de clientes"]

    prompts.choices.append([])
    window.ui.actionPrintReports.trigger()
    assert prompts.last == ("warning", "No se ha seleccionado ningún informe.")  # bug F3

    prompts.choices.append(["Listado de conductores"])  # bug F2: it printed the clients list
    window.ui.actionPrintReports.trigger()
    assert [p.name.split("_")[-1] for p in prompts.opened] == ["listadoconductores.pdf"]

    prompts.choices.append(["Listado de conductores", "Listado de clientes"])
    window.ui.actionPrintReports.trigger()
    assert len(prompts.opened) == 3


def test_close_asks_for_confirmation(window, prompts):
    prompts.exit_answer = False
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    prompts.exit_answer = True
    window.closeEvent(event)
    assert event.isAccepted()


def test_about(window, prompts):
    window.ui.actionAbout.trigger()
    assert prompts.messages[-1][0] == "about"


def test_clear_forms(window):
    window.ui.txtDriverDni.setText("x")
    window.ui.txtClientDni.setText("y")
    window.ui.txtInvoiceClientDni.setText("z")
    window.ui.actionClearForms.trigger()
    assert (window.ui.txtDriverDni.text(), window.ui.txtClientDni.text()) == ("", "")
    assert window.ui.txtInvoiceClientDni.text() == ""


def test_backup_and_restore(window, prompts, conn, tmp_path):
    DriverService(conn).register(make_driver())
    archive = tmp_path / "copy.zip"

    window.ui.actionBackupCreate.trigger()  # cancelled
    assert prompts.messages == []
    prompts.files.append(archive)
    window.ui.actionBackupCreate.trigger()
    assert prompts.last == ("info", f"Copia de seguridad guardada en:\n{archive}")

    DriverService(conn).register(make_driver(dni="00000000T"))
    prompts.files.append(archive)
    prompts.confirm_answers.append(False)
    window.ui.actionBackupRestore.trigger()
    assert len(DriverService(conn).list()) == 2  # declined: nothing restored

    prompts.files.append(archive)
    window.ui.actionBackupRestore.trigger()
    assert prompts.last == ("info", "Copia de seguridad restaurada.")
    assert len(DriverService(conn).list()) == 1
    assert len(table_texts(window.ui.tblDrivers, 0)) == 1  # screen refreshed


def test_restore_reports_invalid_archive(window, prompts, tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_text("nope")
    prompts.files.append(bad)
    window.ui.actionBackupRestore.trigger()
    assert prompts.last == (
        "warning",
        "La copia de seguridad no es válida: no es un fichero .zip legible.",
    )


def test_restore_legacy_backup_shows_report(window, prompts, tmp_path):
    import zipfile

    from tests.legacy_samples import build_legacy_db

    archive = tmp_path / "old.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(build_legacy_db(tmp_path / "bbdd.sqlite"), "bbdd.sqlite")
    prompts.files.append(archive)
    window.ui.actionBackupRestore.trigger()
    kind, text, detail = prompts.messages[-1]
    assert kind == "info" and "versión anterior" in text
    assert "drivers: 4 leídos, 3 importados" in detail


def test_export_and_import(window, prompts, conn, tmp_path):
    DriverService(conn).register(make_driver())
    ClientService(conn).register(make_client())

    window.ui.actionDriversExport.trigger()  # cancelled: no message (bug F4)
    assert prompts.messages == []
    prompts.files.append(tmp_path / "d.xlsx")
    window.ui.actionDriversExport.trigger()
    assert prompts.last[1].startswith("Se han exportado 1 conductores")
    prompts.files.append(tmp_path / "c.xlsx")
    window.ui.actionClientsExport.trigger()
    assert prompts.last[1].startswith("Se han exportado 1 clientes")

    prompts.files.append(tmp_path / "d.xlsx")
    window.ui.actionDriversImport.trigger()
    kind, text, detail = prompts.messages[-1]
    assert (kind, text) == (
        "warning",
        "Se han importado 0 de 1 conductores.\n1 filas no se han importado.",
    )
    assert detail == "Fila 2: Ya existe un conductor con ese DNI."

    conn.execute("DELETE FROM clients")
    prompts.files.append(tmp_path / "c.xlsx")
    window.ui.actionClientsImport.trigger()
    assert prompts.last == ("info", "Se han importado 1 de 1 clientes.")
    assert table_texts(window.ui.tblClients, 1) == ["So Factive"]

    window.ui.actionClientsImport.trigger()  # cancelled
    assert prompts.last == ("info", "Se han importado 1 de 1 clientes.")


def test_import_lists_at_most_15_rejections(window, prompts, tmp_path):
    path = tmp_path / "many.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["DNI", "Razón social", "Dirección", "Teléfono", "Provincia", "Localidad"])
    for _ in range(20):
        sheet.append(["bad", "x", "x", "612345678", "Pontevedra", "Vigo"])
    workbook.save(path)
    prompts.files.append(path)
    window.ui.actionClientsImport.trigger()
    detail = prompts.messages[-1][2].splitlines()
    assert len(detail) == 16
    assert detail[-1] == "… y 5 más."


@pytest.mark.parametrize("size", [(1280, 720), (1600, 950)])
def test_cards_and_tables_share_their_edges(window, size):
    """Each tab's card and its tables must line up left and right at any window size."""
    window.resize(*size)
    window.show()
    ui = window.ui
    for tab, card, tables in (
        (0, ui.driverForm, ui.tblDrivers),
        (1, ui.invoiceForm, ui.invoiceTablesFrame),
        (2, ui.clientForm, ui.tblClients),
    ):
        ui.mainTabs.setCurrentIndex(tab)
        QApplication.processEvents()
        card_x, tables_x = (w.mapTo(window, QPoint(0, 0)).x() for w in (card, tables))
        assert (card_x, card_x + card.width()) == (tables_x, tables_x + tables.width())
