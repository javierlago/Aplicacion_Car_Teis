from datetime import date

import pytest
from PyQt6.QtCore import QDir
from PyQt6.QtWidgets import QDialog, QMessageBox

from carteis import paths
from carteis.ui.main_window import MainWindow

QDir.addSearchPath("img", str(paths.IMAGES_DIR))  # done by create_application in the app

TODAY = date(2026, 10, 11)


class FakePrompts:
    """Records what the UI tells the user and answers its questions from queues."""

    def __init__(self, _parent=None) -> None:
        self.messages: list[tuple[str, str, str]] = []
        self.confirm_answers: list[bool] = []
        self.files: list = []
        self.dates: list = []
        self.calendar_opened_on: list = []
        self.exit_answer = True

    def info(self, text, detail=""):
        self.messages.append(("info", text, detail))

    def warning(self, text, detail=""):
        self.messages.append(("warning", text, detail))

    def confirm(self, text):
        self.messages.append(("confirm", text, ""))
        return self.confirm_answers.pop(0) if self.confirm_answers else True

    def confirm_exit(self):
        return self.exit_answer

    def about(self):
        self.messages.append(("about", "", ""))

    def pick_date(self, initial=None):
        self.calendar_opened_on.append(initial)
        return self.dates.pop(0) if self.dates else None

    def save_file(self, _title, _suggested, _filter):
        return self.files.pop(0) if self.files else None

    def open_file(self, _title, _filter):
        return self.files.pop(0) if self.files else None

    @property
    def last(self) -> tuple[str, str]:
        kind, text, _ = self.messages[-1]
        return kind, text


@pytest.fixture(autouse=True)
def no_real_dialogs(monkeypatch):
    """Fail instead of hanging if the UI opens a dialog without going through Prompts."""

    def refuse(self, *args):
        raise AssertionError(f"Unexpected modal dialog: {type(self).__name__}")

    monkeypatch.setattr(QMessageBox, "exec", refuse)
    monkeypatch.setattr(QDialog, "exec", refuse)


@pytest.fixture
def window(qtbot, conn):
    window = MainWindow(conn, prompts_factory=FakePrompts, today=lambda: TODAY)
    qtbot.addWidget(window)
    return window


@pytest.fixture
def prompts(window) -> FakePrompts:
    return window.prompts


def click_row(view, row: int) -> None:
    view.clicked.emit(view.model().index(row, 0))


def table_texts(view, column: int) -> list[str]:
    model = view.model()
    return [model.index(row, column).data() for row in range(model.rowCount())]
