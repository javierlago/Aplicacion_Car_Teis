import logging
import re
import sys

import pytest
from PyQt6.QtWidgets import QMessageBox

from carteis import app, paths


@pytest.fixture
def isolated_logger():
    logger = logging.getLogger("carteis")
    handlers = list(logger.handlers)
    yield logger
    for handler in logger.handlers:
        if handler not in handlers:
            handler.close()
    logger.handlers = handlers


def test_ensure_database_copies_seed_once(tmp_path):
    target = tmp_path / "data" / "carteis.sqlite"
    assert paths.ensure_database(target) == target
    assert target.read_bytes() == paths.SEED_DATABASE.read_bytes()
    target.write_bytes(b"user data")
    paths.ensure_database(target)
    assert target.read_bytes() == b"user data"


def test_database_path_override(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.DATABASE_ENV, str(tmp_path / "x.sqlite"))
    assert paths.database_path() == tmp_path / "x.sqlite"
    monkeypatch.delenv(paths.DATABASE_ENV)
    assert paths.database_path().name == "carteis.sqlite"
    assert paths.log_path().name == "carteis.log"


def test_bundled_resources_exist():
    assert paths.STYLE_SHEET.is_file()
    assert paths.SEED_DATABASE.is_file()
    assert (paths.IMAGES_DIR / "taxiIcon.png").is_file()


def test_open_database_migrates(tmp_path):
    conn = app.open_database(tmp_path / "new.sqlite")
    assert conn.execute("PRAGMA user_version").fetchone()[0] >= 1
    conn.close()


def test_create_application(qapp):
    created = app.create_application(["carteis"])
    assert created is qapp
    assert created.applicationName() == "CarTeis"
    assert "role" in created.styleSheet()
    qapp.setStyleSheet("")


def test_exception_hook_logs_and_tells_the_user(monkeypatch, tmp_path, isolated_logger):
    log_file = tmp_path / "logs" / "carteis.log"
    app.configure_logging(log_file)
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: shown.append(args))
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    app.install_exception_hook(log_file)
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    assert "boom" in log_file.read_text(encoding="utf-8")
    assert str(log_file) in shown[0][2]


def test_main_starts_and_closes(monkeypatch, qapp, tmp_path, isolated_logger):
    monkeypatch.setenv(paths.DATABASE_ENV, str(tmp_path / "carteis.sqlite"))
    monkeypatch.setattr(paths, "log_path", lambda: tmp_path / "carteis.log")
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(qapp, "exec", lambda: 0)
    shown = []
    from carteis.ui import main_window

    monkeypatch.setattr(main_window.MainWindow, "showMaximized", lambda self: shown.append(self))
    assert app.main(["carteis"]) == 0
    assert (tmp_path / "carteis.sqlite").exists()
    assert shown and shown[0].ui.tblDrivers.model().rowCount() == 13  # seed data, active only
    shown[0].prompts.confirm_exit = lambda: True
    shown[0].close()
    qapp.setStyleSheet("")


def test_every_referenced_image_exists():
    """Catch icons pointing at missing files (the legacy calendar icon never existed)."""
    sources = paths.RESOURCES_DIR.parent / "carteis"
    names = {
        name
        for source in sources.rglob("*.py")
        for name in re.findall(r'"img:([^"]+)"', source.read_text(encoding="utf-8"))
    }
    assert names, "no img: references found"
    assert sorted(n for n in names if not (paths.IMAGES_DIR / n).is_file()) == []
