"""The real Prompts and dialogs, with exec() intercepted so nothing blocks."""

from datetime import date
from pathlib import Path

import pytest
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QCheckBox, QDialog, QFileDialog, QMessageBox, QWidget

from carteis.ui.dialogs import AboutDialog, CalendarDialog, ExitDialog
from carteis.ui.prompts import Prompts
from carteis.ui.table_models import Column, RecordTableModel


@pytest.fixture
def parent(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def shown(monkeypatch):
    """Capture message boxes instead of showing them; answer with ``shown.answer``."""

    class Shown(list):
        answer = QMessageBox.StandardButton.Ok

    boxes = Shown()

    def fake_exec(box):
        boxes.append(box)
        return boxes.answer

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    return boxes


def test_info_and_warning(parent, shown):
    prompts = Prompts(parent)
    prompts.info("Hecho", detail="más")
    prompts.warning("Cuidado")
    assert [(b.icon(), b.text(), b.windowTitle()) for b in shown] == [
        (QMessageBox.Icon.Information, "Hecho", "CarTeis"),
        (QMessageBox.Icon.Warning, "Cuidado", "CarTeis"),
    ]
    assert shown[0].detailedText() == "más"


def test_confirm(parent, shown):
    prompts = Prompts(parent)
    shown.answer = QMessageBox.StandardButton.Yes
    assert prompts.confirm("¿Seguro?") is True
    assert shown[0].button(QMessageBox.StandardButton.Yes).text() == "Sí"
    assert shown[0].defaultButton() is shown[0].button(QMessageBox.StandardButton.No)
    shown.answer = QMessageBox.StandardButton.No
    assert prompts.confirm("¿Seguro?") is False


@pytest.mark.parametrize("result, expected", [(1, True), (0, False)])
def test_confirm_exit(monkeypatch, parent, result, expected):
    monkeypatch.setattr(ExitDialog, "exec", lambda self: result)
    assert Prompts(parent).confirm_exit() is expected


def test_about(monkeypatch, parent):
    opened = []
    monkeypatch.setattr(AboutDialog, "exec", lambda self: opened.append(self))
    Prompts(parent).about()
    assert isinstance(opened[0], AboutDialog)


def test_pick_date(monkeypatch, parent):
    def accept_with(day):
        def fake_exec(dialog):
            dialog.ui.calendar.setSelectedDate(QDate(day.year, day.month, day.day))
            return QDialog.DialogCode.Accepted

        return fake_exec

    monkeypatch.setattr(CalendarDialog, "exec", accept_with(date(2024, 2, 29)))
    assert Prompts(parent).pick_date(date(2024, 1, 1)) == date(2024, 2, 29)
    monkeypatch.setattr(CalendarDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    assert Prompts(parent).pick_date() is None


def test_file_dialogs(monkeypatch, parent):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: ("C:/x/copy.zip", ""))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: ("", ""))
    prompts = Prompts(parent)
    assert prompts.save_file("t", "copy.zip", "*.zip") == Path("C:/x/copy.zip")
    assert prompts.open_file("t", "*.zip") is None


def test_calendar_dialog_accepts_on_click(parent):
    dialog = CalendarDialog(parent, date(2023, 5, 6))
    assert dialog.selected_date() == date(2023, 5, 6)
    dialog.ui.calendar.clicked.emit(QDate(2023, 5, 7))
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_about_and_exit_buttons(parent):
    about = AboutDialog(parent)
    about.ui.btnClose.click()
    assert about.result() == QDialog.DialogCode.Accepted
    exit_dialog = ExitDialog(parent)
    exit_dialog.ui.btnCancel.click()
    assert exit_dialog.result() == QDialog.DialogCode.Rejected
    exit_dialog.ui.btnAccept.click()
    assert exit_dialog.result() == QDialog.DialogCode.Accepted


def test_table_model_edges():
    model = RecordTableModel([Column[str]("Texto", lambda s: s)])
    model.set_records(["a"])
    assert model.data(model.index(5, 0)) is None  # invalid index
    assert model.data(model.index(0, 0), role=999) is None
    assert model.headerData(0, Qt.Orientation.Vertical) is None
    assert model.rowCount(model.index(0, 0)) == 0  # no children


def test_choose(monkeypatch, parent):
    def tick_second_and(result):
        def fake_exec(dialog):
            dialog.findChildren(QCheckBox)[1].setChecked(True)
            return result

        return fake_exec

    monkeypatch.setattr(QDialog, "exec", tick_second_and(QDialog.DialogCode.Accepted))
    assert Prompts(parent).choose("t", "Elige", ["Uno", "Dos"]) == ["Dos"]
    monkeypatch.setattr(QDialog, "exec", tick_second_and(QDialog.DialogCode.Rejected))
    assert Prompts(parent).choose("t", "Elige", ["Uno", "Dos"]) is None


def test_open_document_falls_back_to_a_message(monkeypatch, parent, shown, tmp_path):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    Prompts(parent).open_document(tmp_path / "a.pdf")
    assert opened[0].toLocalFile().endswith("a.pdf")
    assert shown == []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: False)
    Prompts(parent).open_document(tmp_path / "a.pdf")
    assert "Documento guardado en" in shown[0].text()
