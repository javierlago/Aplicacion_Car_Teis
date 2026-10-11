import sqlite3
from collections.abc import Callable
from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QLabel, QMainWindow, QWidget

from carteis import __version__
from carteis.services import BackupService, ImportResult, SpreadsheetService
from carteis.ui.forms import user_action
from carteis.ui.generated.main_window import Ui_MainWindow
from carteis.ui.prompts import Prompts
from carteis.ui.tabs.clients import ClientsTab
from carteis.ui.tabs.drivers import DriversTab
from carteis.ui.tabs.invoicing import InvoicingTab

_WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_EXCEL_FILTER = "Libro de Excel (*.xlsx)"
_BACKUP_FILTER = "Copia de seguridad (*.zip)"
_MAX_LISTED_REJECTIONS = 15


def status_date(day: date) -> str:
    """``domingo-11-10-2026``, as the legacy status bar showed it."""
    return f"{_WEEKDAYS[day.weekday()]}-{day:%d-%m-%Y}"


class MainWindow(QMainWindow):
    def __init__(
        self,
        conn: sqlite3.Connection,
        prompts_factory: Callable[[QWidget], Prompts] = Prompts,
        today: Callable[[], date] = date.today,
    ) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.prompts = prompts_factory(self)
        self.field_widgets: dict[str, QWidget] = {}
        self._backups = BackupService(conn)
        self._sheets = SpreadsheetService(conn)

        self.invoicing = InvoicingTab(self.ui, conn, self.prompts)
        self.drivers = DriversTab(self.ui, conn, self.prompts, self.invoicing.reload_drivers)
        self.clients = ClientsTab(self.ui, conn, self.prompts)

        ui = self.ui
        ui.actionExit.triggered.connect(self.close)
        ui.actionToolbarExit.triggered.connect(self.close)
        ui.actionAbout.triggered.connect(self.prompts.about)
        ui.actionClearForms.triggered.connect(self.clear_forms)
        ui.actionBackupCreate.triggered.connect(self._create_backup)
        ui.actionBackupRestore.triggered.connect(self._restore_backup)
        ui.actionDriversExport.triggered.connect(self._export_drivers)
        ui.actionDriversImport.triggered.connect(self._import_drivers)
        ui.actionClientsExport.triggered.connect(self._export_clients)
        ui.actionClientsImport.triggered.connect(self._import_clients)
        for action in (
            ui.actionReportDrivers,
            ui.actionReportClients,
            ui.actionReportInvoice,
            ui.actionPrintReports,
        ):
            action.setEnabled(False)  # the PDF reports are rewritten in phase 5
            action.setToolTip("Los informes estarán disponibles en la próxima versión.")

        self._status_date = QLabel(status_date(today()), self)
        self._status_date.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        ui.statusbar.addPermanentWidget(self._status_date, 1)
        version = QLabel(f"Versión: {__version__}", self)
        version.setAlignment(Qt.AlignmentFlag.AlignRight)
        ui.statusbar.addPermanentWidget(version, 0)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.prompts.confirm_exit():
            event.accept()
        else:
            event.ignore()

    def clear_forms(self) -> None:
        self.drivers.clear()
        self.clients.clear()
        self.invoicing.clear()

    def reload_all(self) -> None:
        """After a restore or import, everything on screen may be stale."""
        self.invoicing.reload_drivers()
        self.clear_forms()

    # ---- backups ---------------------------------------------------------------------

    @user_action
    def _create_backup(self) -> None:
        path = self.prompts.save_file(
            "Crear copia de seguridad", self._backups.default_filename(), _BACKUP_FILTER
        )
        if path:
            self._backups.create(path)
            self.prompts.info(f"Copia de seguridad guardada en:\n{path}")

    @user_action
    def _restore_backup(self) -> None:
        path = self.prompts.open_file("Restaurar copia de seguridad", _BACKUP_FILTER)
        if not path or not self.prompts.confirm(
            "Se reemplazarán todos los datos actuales por los de la copia. ¿Continuar?"
        ):
            return
        report = self._backups.restore(path)
        self.reload_all()
        if report is None:
            self.prompts.info("Copia de seguridad restaurada.")
        else:
            self.prompts.info(
                "Copia de seguridad de la versión anterior restaurada y convertida.",
                detail=str(report),
            )

    # ---- spreadsheets ----------------------------------------------------------------

    def _export(self, title: str, name: str, export: Callable, noun: str) -> None:
        path = self.prompts.save_file(title, f"{name}.xlsx", _EXCEL_FILTER)
        if path:  # fixes bug F4: no success message when the dialog is cancelled
            count = export(path)
            self.prompts.info(f"Se han exportado {count} {noun} a:\n{path}")

    @user_action
    def _export_drivers(self) -> None:
        self._export(
            "Exportar conductores", "conductores", self._sheets.export_drivers, "conductores"
        )

    @user_action
    def _export_clients(self) -> None:
        self._export("Exportar clientes", "clientes", self._sheets.export_clients, "clientes")

    def _import(self, title: str, run: Callable[..., ImportResult], noun: str) -> None:
        path = self.prompts.open_file(title, _EXCEL_FILTER)
        if not path:
            return
        result = run(path)
        self.reload_all()
        text = f"Se han importado {result.inserted} de {result.total} {noun}."
        if not result.rejected:
            self.prompts.info(text)
            return
        lines = [f"Fila {r.row}: {r.reason}" for r in result.rejected[:_MAX_LISTED_REJECTIONS]]
        if len(result.rejected) > _MAX_LISTED_REJECTIONS:
            lines.append(f"… y {len(result.rejected) - _MAX_LISTED_REJECTIONS} más.")
        self.prompts.warning(
            f"{text}\n{len(result.rejected)} filas no se han importado.", detail="\n".join(lines)
        )

    @user_action
    def _import_drivers(self) -> None:
        self._import("Importar conductores", self._sheets.import_drivers, "conductores")

    @user_action
    def _import_clients(self) -> None:
        self._import("Importar clientes", self._sheets.import_clients, "clientes")
