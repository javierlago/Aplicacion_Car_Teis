"""Every modal interaction with the user goes through :class:`Prompts`.

Controllers never open dialogs themselves, so tests can swap in a fake that records
messages and returns canned answers instead of blocking on a modal window.
"""

from collections.abc import Sequence
from datetime import date
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from carteis.ui.dialogs import AboutDialog, CalendarDialog, ExitDialog

_TITLE = "CarTeis"


class Prompts:
    def __init__(self, parent: QWidget) -> None:
        self._parent = parent

    def _box(self, icon: QMessageBox.Icon, text: str, detail: str = "") -> QMessageBox:
        box = QMessageBox(icon, _TITLE, text, parent=self._parent)
        box.setWindowIcon(QIcon("img:taxiIcon.png"))
        if detail:
            box.setDetailedText(detail)
        return box

    def info(self, text: str, detail: str = "") -> None:
        self._box(QMessageBox.Icon.Information, text, detail).exec()

    def warning(self, text: str, detail: str = "") -> None:
        self._box(QMessageBox.Icon.Warning, text, detail).exec()

    def confirm(self, text: str) -> bool:
        box = self._box(QMessageBox.Icon.Question, text)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.button(QMessageBox.StandardButton.Yes).setText("Sí")
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    def confirm_exit(self) -> bool:
        return ExitDialog(self._parent).exec() == QDialog.DialogCode.Accepted

    def about(self) -> None:
        AboutDialog(self._parent).exec()

    def pick_date(self, initial: date | None = None) -> date | None:
        dialog = CalendarDialog(self._parent, initial)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_date()
        return None

    def save_file(self, title: str, suggested_name: str, file_filter: str) -> Path | None:
        path, _ = QFileDialog.getSaveFileName(self._parent, title, suggested_name, file_filter)
        return Path(path) if path else None

    def open_file(self, title: str, file_filter: str) -> Path | None:
        path, _ = QFileDialog.getOpenFileName(self._parent, title, "", file_filter)
        return Path(path) if path else None

    def choose(self, title: str, text: str, options: Sequence[str]) -> list[str] | None:
        """Tick any of ``options``. ``None`` if cancelled; may be an empty list."""
        dialog = QDialog(self._parent)
        dialog.setWindowTitle(title)
        dialog.setWindowIcon(QIcon("img:impresora.png"))
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(text, dialog))
        boxes = [QCheckBox(option, dialog) for option in options]
        for box in boxes:
            layout.addWidget(box)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Aceptar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return [box.text() for box in boxes if box.isChecked()]

    def open_document(self, path: Path) -> None:
        """Open a generated file with the system viewer; say where it is if that fails."""
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self.info(f"Documento guardado en:\n{path}")
