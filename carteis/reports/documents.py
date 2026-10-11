"""The three reports: drivers list, clients list and a client invoice."""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from reportlab.pdfgen.canvas import Canvas

from carteis import config
from carteis.config import Company
from carteis.domain.formatting import format_date, format_money
from carteis.domain.models import Client, Driver, Invoice
from carteis.reports.pdf import Align, Report, Table, TableColumn, fit

_LIST_ROWS = {"header_y": 675, "first_row_y": 635, "bottom_y": 80}


def mask_dni(dni: str) -> str:
    """Hide all but the last characters, as the legacy client list did."""
    return "XXXXXX" + dni[6:]


def drivers_report(
    path: Path,
    drivers: Sequence[Driver],
    generated_at: datetime,
    company: Company = config.COMPANY,
    logo: Path | None = None,
) -> Path:
    report = Report(path, "Listado de Conductores", company, generated_at, logo)
    table = Table(
        [
            TableColumn("Código", 60, 55),
            TableColumn("Apellidos", 120, 75),
            TableColumn("Nombre", 200, 95),
            TableColumn("Móvil", 300, 105),
            TableColumn("Licencias", 410, 65),
            TableColumn("Fecha Baja", 480, 60),
        ],
        **_LIST_ROWS,
    )
    table.draw(
        report,
        (
            [
                str(d.id),
                d.surname,
                d.name,
                d.phone,
                "-".join(sorted(d.licenses)),
                format_date(d.left_on),
            ]
            for d in drivers
        ),
    )
    report.save()
    return path


def clients_report(
    path: Path,
    clients: Sequence[Client],
    generated_at: datetime,
    company: Company = config.COMPANY,
    logo: Path | None = None,
) -> Path:
    report = Report(path, "Listado de Clientes", company, generated_at, logo)
    table = Table(
        [
            TableColumn("Código", 60, 55),
            TableColumn("DNI", 120, 55),
            TableColumn("Razón social", 180, 115),
            TableColumn("Municipio", 300, 105),
            TableColumn("Provincia", 410, 65),
            TableColumn("Baja", 480, 60),
        ],
        **_LIST_ROWS,
    )
    table.draw(
        report,
        (
            [
                str(c.id),
                mask_dni(c.dni),
                c.company_name,
                c.municipality,
                c.province,
                format_date(c.left_on),
            ]
            for c in clients
        ),
    )
    report.save()
    return path


def _client_block(invoice: Invoice, client: Client):
    """The 'Datos del Cliente' box, repeated on every page of the invoice."""

    def draw(canvas: Canvas) -> None:
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawString(210, 785, "Datos del Cliente")
        fields = [
            ("Nº de factura", str(invoice.id)),
            ("Fecha de la factura", format_date(invoice.issued_on)),
            ("DNI/CIF", client.dni),
            ("Razón Social", client.company_name),
            ("Dirección", client.address),
            ("Teléfono", client.phone),
            ("Provincia", client.province),
            ("Municipio", client.municipality),
        ]
        for index, (label, value) in enumerate(fields):
            y = 770 - 15 * index
            canvas.setFont("Helvetica-Bold", 7)
            canvas.drawString(210, y, label)
            canvas.setFont("Helvetica", 9)
            canvas.drawString(290, y, fit(value, 145, "Helvetica", 9))

    return draw


def invoice_report(
    path: Path,
    invoice: Invoice,
    client: Client,
    generated_at: datetime,
    company: Company = config.COMPANY,
    logo: Path | None = None,
) -> Path:
    report = Report(
        path,
        "Factura Cliente",
        company,
        generated_at,
        logo,
        title_y=645,
        decorate=_client_block(invoice, client),
    )
    table = Table(
        [
            TableColumn("Id Viaje", 85, 50, Align.CENTER),
            TableColumn("Origen", 155, 90, Align.CENTER),
            TableColumn("Destino", 255, 90, Align.CENTER),
            TableColumn("Kilómetros", 335, 60, Align.CENTER),
            TableColumn("Tarifa", 415, 60, Align.CENTER),
            TableColumn("Total", 485, 60, Align.CENTER),
        ],
        header_y=625,
        first_row_y=605,
        bottom_y=120,
        font_size=10,
    )
    y = table.draw(
        report,
        (
            [
                str(t.id),
                t.origin.municipality,
                t.destination.municipality,
                str(t.km),
                format_money(t.rate),
                format_money(t.amount),
            ]
            for t in invoice.trips
        ),
    )

    if y - 60 < 80:  # the totals would run into the footer
        report.new_page()
        y = 605
    totals = invoice.totals
    vat_percent = f"{(config.VAT_RATE * 100).normalize():f}"
    canvas = report.canvas
    for offset, label, value in (
        (10, "Subtotal:", totals.subtotal),
        (30, f"IVA {vat_percent}%:", totals.vat),
        (50, "Total:", totals.total),
    ):
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(400, y - offset, label)
        canvas.setFont("Helvetica", 10)
        canvas.drawRightString(520, y - offset, format_money(value))
    report.save()
    return path
