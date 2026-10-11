from datetime import datetime

import pytest
from pypdf import PdfReader

from carteis.domain.errors import NotFoundError
from carteis.services import ClientService, DriverService, InvoicingService, ReportService
from tests.factories import VIGO, make_client, make_driver


@pytest.fixture
def reports(conn, tmp_path):
    return ReportService(conn, tmp_path / "CarTeis", now=lambda: datetime(2026, 10, 11, 18, 30, 5))


def text_of(path):
    return " ".join(" ".join(page.extract_text().split()) for page in PdfReader(path).pages)


def test_lists_include_active_and_inactive(conn, reports, tmp_path):
    drivers = DriverService(conn)
    drivers.register(make_driver(dni="12345678Z", surname="Activo"))
    gone = drivers.register(make_driver(dni="00000000T", surname="Inactivo"))
    drivers.deactivate(gone.id)
    ClientService(conn).register(make_client())

    drivers_pdf = reports.drivers_list()
    assert drivers_pdf == tmp_path / "CarTeis/Informes/2026_10_11_18_30_05_listadoconductores.pdf"
    assert "Activo" in text_of(drivers_pdf) and "Inactivo" in text_of(drivers_pdf)

    clients_pdf = reports.clients_list()
    assert clients_pdf.name == "2026_10_11_18_30_05_listadoclientes.pdf"
    assert "So Factive" in text_of(clients_pdf)


def test_invoice(conn, reports, tmp_path):
    driver = DriverService(conn).register(make_driver())
    client = ClientService(conn).register(make_client())
    service = InvoicingService(conn)
    invoice = service.create_invoice(client.dni, driver.id, [service.new_trip(VIGO, VIGO, 10)])

    path = reports.invoice(invoice.id)
    assert path.parent == tmp_path / "CarTeis" / "Facturas"
    assert path.name == f"2026_10_11_18_30_05_factura_{invoice.id}.pdf"
    assert "Total: 2,42 €" in text_of(path)


def test_unknown_invoice(reports):
    with pytest.raises(NotFoundError, match="factura número 99"):
        reports.invoice(99)
