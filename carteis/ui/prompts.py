"""Every modal interaction with the user goes through :class:`Prompts`.

Controllers never open dialogs themselves, so tests can swap in a fake that records
messages and returns canned answers instead of blocking on a modal window.
"""

from datetime import date
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWidget

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
