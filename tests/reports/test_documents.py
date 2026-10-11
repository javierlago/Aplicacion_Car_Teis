from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pypdf import PdfReader

from carteis import config
from carteis.domain.models import Invoice, Trip
from carteis.domain.pricing import Location
from carteis.reports import clients_report, drivers_report, invoice_report
from carteis.reports.documents import mask_dni
from carteis.reports.pdf import fit
from tests.factories import CANGAS, FERROL, VIGO, make_client, make_driver

NOW = datetime(2026, 10, 11, 18, 30, 5)
LOGO = Path(__file__).resolve().parents[2] / "img" / "IconoInfome.png"


def pages(path: Path) -> list[str]:
    """Text of each page, with the line breaks between drawn strings turned into spaces."""
    return [" ".join(page.extract_text().split()) for page in PdfReader(path).pages]


def test_fit_shortens_with_ellipsis():
    assert fit("Vigo", 100, "Helvetica", 9) == "Vigo"
    short = fit("Every Good Good After Logo Limited Company", 60, "Helvetica", 9)
    assert short.endswith("…") and len(short) < 20
    assert fit("abc", 0, "Helvetica", 9) == "…"


def test_mask_dni():
    assert mask_dni("53854586V") == "XXXXXX86V"


def test_header_and_footer_on_every_page(tmp_path):
    drivers = [make_driver(id=i, dni="12345678Z", surname=f"Surname {i:02}") for i in range(1, 41)]
    path = drivers_report(tmp_path / "d.pdf", drivers, NOW, logo=LOGO)
    texts = pages(path)
    assert len(texts) == 2  # 28 rows fit on a page
    for number, text in enumerate(texts, start=1):
        assert "Transportes Teis" in text
        assert "CIF: A12345678" in text
        assert "Listado de Conductores" in text
        assert "11-10-2026 18:30:05" in text
        assert f"Página {number}" in text
        assert "Código Apellidos Nombre Móvil Licencias Fecha Baja" in text  # header, unshortened
    assert "Surname 01" in texts[0] and "Surname 40" in texts[1]


def test_drivers_report_rows(tmp_path):
    driver = make_driver(id=7, left_on=date(2024, 1, 31))
    text = pages(drivers_report(tmp_path / "d.pdf", [driver], NOW))[0]
    assert "7 Gómez Ana 612345678 A-B 31/01/2024" in text


def test_clients_report_masks_dni(tmp_path):
    client = make_client(id=43)
    text = pages(clients_report(tmp_path / "c.pdf", [client], NOW, logo=LOGO))[0]
    assert "Listado de Clientes" in text
    assert "43 XXXXXX86V So Factive Cangas Pontevedra" in text
    assert "53854586V" not in text


def test_empty_list_still_has_a_page(tmp_path):
    assert len(pages(clients_report(tmp_path / "c.pdf", [], NOW))) == 1


def test_missing_logo_is_ignored(tmp_path):
    path = clients_report(tmp_path / "c.pdf", [], NOW, logo=tmp_path / "nope.png")
    assert path.is_file()


def make_invoice(trips):
    return Invoice(
        id=12, client_dni="53854586V", driver_id=1, issued_on=date(2024, 2, 27), trips=trips
    )


def trip(trip_id, origin=VIGO, destination=FERROL, km=12, rate="0.80"):
    return Trip(id=trip_id, origin=origin, destination=destination, km=km, rate=Decimal(rate))


def test_invoice_report(tmp_path):
    invoice = make_invoice([trip(1), trip(2, destination=CANGAS, km=10, rate="0.40")])
    path = invoice_report(tmp_path / "f.pdf", invoice, make_client(), NOW, logo=LOGO)
    (text,) = pages(path)
    assert "Factura Cliente" in text
    assert "Datos del Cliente" in text
    assert "Nº de factura 12" in text
    assert "Fecha de la factura 27/02/2024" in text
    assert "DNI/CIF 53854586V" in text
    assert "Razón Social So Factive" in text
    assert "1 Vigo Ferrol 12 0,80 € 9,60 €" in text
    assert "2 Vigo Cangas 10 0,40 € 4,00 €" in text
    assert "Subtotal: 13,60 €" in text
    assert "IVA 21%: 2,86 €" in text
    assert "Total: 16,46 €" in text


def test_invoice_totals_move_to_a_new_page_when_needed(tmp_path):
    invoice = make_invoice([trip(i, km=10, rate="0.20") for i in range(1, 26)])
    texts = pages(invoice_report(tmp_path / "f.pdf", invoice, make_client(), NOW))
    assert len(texts) == 2
    assert "25 Vigo Ferrol" in texts[0]
    assert "Total: 60,50 €" in texts[1]
    assert "Datos del Cliente" in texts[1]  # client block repeated


def test_invoice_with_many_trips_repeats_the_table_header(tmp_path):
    invoice = make_invoice([trip(i, km=1, rate="0.20") for i in range(1, 41)])
    texts = pages(invoice_report(tmp_path / "f.pdf", invoice, make_client(), NOW))
    assert len(texts) == 2
    assert "Id Viaje" in texts[1] and "40 Vigo Ferrol" in texts[1]
    assert "Total: 9,68 €" in texts[1]


def test_invoice_without_trips_shows_zero_totals(tmp_path):
    (text,) = pages(invoice_report(tmp_path / "f.pdf", make_invoice([]), make_client(), NOW))
    assert "Total: 0,00 €" in text


def test_long_names_are_shortened(tmp_path):
    long_place = Location("Pontevedra", "Municipio con un nombre larguísimo de verdad")
    invoice = make_invoice([trip(1, origin=long_place)])
    client = make_client(company_name="Una razón social tan larga que no cabe en la caja")
    (text,) = pages(invoice_report(tmp_path / "f.pdf", invoice, client, NOW))
    assert "Municipio con un nombre larguísimo de verdad" not in text
    assert "…" in text


@pytest.mark.parametrize("rate, label", [("0.21", "IVA 21%"), ("0.10", "IVA 10%")])
def test_vat_label_follows_config(monkeypatch, tmp_path, rate, label):
    monkeypatch.setattr(config, "VAT_RATE", Decimal(rate))
    (text,) = pages(invoice_report(tmp_path / "f.pdf", make_invoice([]), make_client(), NOW))
    assert label in text


def test_company_details_come_from_config(tmp_path):
    company = replace(config.COMPANY, name="Taxis Vigo", tax_id="B87654321")
    (text,) = pages(clients_report(tmp_path / "c.pdf", [], NOW, company=company))
    assert "Taxis Vigo" in text and "CIF: B87654321" in text
