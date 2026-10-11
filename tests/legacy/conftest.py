from unittest.mock import MagicMock

import pytest
from PyQt6 import QtWidgets

import var
import Ventanas


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    """Fail fast instead of hanging forever when code under test opens a modal dialog."""

    def _refuse(self, *args, **kwargs):
        raise AssertionError(f"Unexpected modal dialog: {self.text()!r}")

    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", _refuse)


@pytest.fixture
def messages(monkeypatch):
    """Capture the legacy warning/info pop-ups instead of showing them."""
    mock = MagicMock(name="Ventanas")
    monkeypatch.setattr(Ventanas.Ventanas, "mensaje_warning", mock.warning)
    monkeypatch.setattr(Ventanas.Ventanas, "ventana_info", mock.info)
    return mock


@pytest.fixture
def fake_ui(qapp, monkeypatch, messages):
    """Replace the global ``var.ui`` with a mock so legacy code runs without the main window.

    ``qapp`` (from pytest-qt) is required because the legacy validators build ``QPixmap``
    objects, which need a ``QGuiApplication``.
    """
    ui = MagicMock(name="ui")
    monkeypatch.setattr(var, "ui", ui, raising=False)
    return ui
