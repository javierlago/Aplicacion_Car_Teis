"""Generate the PDF reports from the database into the user's reports folder."""

import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from carteis.data.repositories import ClientRepository, DriverRepository, InvoiceRepository
from carteis.domain.errors import NotFoundError
from carteis.reports import clients_report, drivers_report, invoice_report

LISTS_FOLDER = "Informes"
INVOICES_FOLDER = "Facturas"


class ReportService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        output_dir: Path,
        logo: Path | None = None,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._drivers = DriverRepository(conn)
        self._clients = ClientRepository(conn)
        self._invoices = InvoiceRepository(conn)
        self._output_dir = output_dir
        self._logo = logo
        self._now = now

    def drivers_list(self) -> Path:
        """All drivers, active and inactive, ordered by surname."""
        now = self._now()
        path = self._target(LISTS_FOLDER, f"{now:%Y_%m_%d_%H_%M_%S}_listadoconductores.pdf")
        return drivers_report(path, self._drivers.list(), now, logo=self._logo)

    def clients_list(self) -> Path:
        """All clients, active and inactive, ordered by company name."""
        now = self._now()
        path = self._target(LISTS_FOLDER, f"{now:%Y_%m_%d_%H_%M_%S}_listadoclientes.pdf")
        return clients_report(path, self._clients.list(), now, logo=self._logo)

    def invoice(self, invoice_id: int) -> Path:
        invoice = self._invoices.get(invoice_id)
        if invoice is None:
            raise NotFoundError(f"No existe la factura número {invoice_id}.")
        client = self._clients.get_by_dni(invoice.client_dni)
        if client is None:  # pragma: no cover - prevented by the foreign key
            raise NotFoundError(f"No existe ningún cliente con el DNI {invoice.client_dni}.")
        now = self._now()
        path = self._target(INVOICES_FOLDER, f"{now:%Y_%m_%d_%H_%M_%S}_factura_{invoice.id}.pdf")
        return invoice_report(path, invoice, client, now, logo=self._logo)

    def _target(self, folder: str, filename: str) -> Path:
        directory = self._output_dir / folder
        directory.mkdir(parents=True, exist_ok=True)
        return directory / filename
