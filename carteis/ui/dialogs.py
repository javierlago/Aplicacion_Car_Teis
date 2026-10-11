"""Thin wrappers around the generated dialogs."""

from datetime import date

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QCalendarWidget, QDialog, QWidget

from carteis import __version__
from carteis.ui.generated.about_dialog import Ui_AboutDialog
from carteis.ui.generated.calendar_dialog import Ui_CalendarDialog
from carteis.ui.generated.exit_dialog import Ui_ExitDialog

ABOUT_TEXT = """
<p align="center" style="font-size: 15pt; font-weight: 600;">CarTeis</p>
<p align="center">Gestión de conductores, clientes y facturación para empresas de taxi.</p>
<p align="center">Versión {version}</p>
<p align="center">Javier Lago Amoedo<br>Proyecto de fin de ciclo · IES de Teis (2023)</p>
"""


class CalendarDialog(QDialog):
    """Pick a date with one click."""

    def __init__(self, parent: QWidget | None = None, initial: date | None = None) -> None:
        super().__init__(parent)
        self.ui = Ui_CalendarDialog()
        self.ui.setupUi(self)
        self.ui.calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader  # no week numbers
        )
        if initial:
            self.ui.calendar.setSelectedDate(QDate(initial.year, initial.month, initial.day))
        self.ui.calendar.clicked.connect(self.accept)

    def selected_date(self) -> date:
        return self.ui.calendar.selectedDate().toPyDate()


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ui = Ui_AboutDialog()
        self.ui.setupUi(self)
        self.ui.txtAbout.setReadOnly(True)
        self.ui.txtAbout.setHtml(ABOUT_TEXT.format(version=__version__))
        self.ui.btnClose.clicked.connect(self.accept)


class ExitDialog(QDialog):
    """Asks for confirmation before closing the app."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ui = Ui_ExitDialog()
        self.ui.setupUi(self)
        self.ui.btnAccept.clicked.connect(self.accept)
        self.ui.btnCancel.clicked.connect(self.reject)
