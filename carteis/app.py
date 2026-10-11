"""Application start-up: wires Qt, logging, the database and the main window together."""

import logging
import sqlite3
import sys
from collections.abc import Sequence
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtCore import QDir
from PyQt6.QtWidgets import QApplication, QMessageBox

from carteis import __version__, paths
from carteis.data.database import connect
from carteis.data.migrations import migrate

log = logging.getLogger("carteis")


def configure_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def install_exception_hook(log_file: Path) -> None:
    """Log unexpected errors and tell the user, instead of PyQt aborting the app."""

    def hook(exc_type, exc, traceback) -> None:
        log.critical("Unhandled exception", exc_info=(exc_type, exc, traceback))
        QMessageBox.critical(
            None,
            "Error inesperado",
            "Ha ocurrido un error inesperado. La operación no se ha completado.\n\n"
            f"Los detalles se han guardado en:\n{log_file}",
        )

    sys.excepthook = hook


def open_database(path: Path) -> sqlite3.Connection:
    conn = connect(path)
    migrate(conn)
    return conn


def create_application(argv: Sequence[str]) -> QApplication:
    app = QApplication.instance() or QApplication(list(argv))
    app.setOrganizationName("CarTeis")
    app.setApplicationName("CarTeis")
    app.setApplicationVersion(__version__)
    QDir.addSearchPath("img", str(paths.IMAGES_DIR))
    app.setStyleSheet(paths.STYLE_SHEET.read_text(encoding="utf-8"))
    return app


def main(argv: Sequence[str] | None = None) -> int:
    app = create_application(sys.argv if argv is None else argv)
    log_file = paths.log_path()
    configure_logging(log_file)
    install_exception_hook(log_file)

    database = paths.ensure_database(paths.database_path())
    log.info("Starting CarTeis %s with database %s", __version__, database)
    conn = open_database(database)

    from carteis.ui.main_window import MainWindow  # after QApplication exists

    window = MainWindow(conn)
    window.showMaximized()
    try:
        return app.exec()
    finally:
        conn.close()
