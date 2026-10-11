from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from carteis.data.database import connect
from carteis.data.legacy_import import import_legacy, main
from carteis.data.repositories import ClientRepository, DriverRepository, InvoiceRepository
from tests.legacy_samples import build_legacy_db

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_LEGACY_DB = REPO_ROOT / "bbdd.sqlite"


@pytest.fixture
def legacy_db(tmp_path):
    return build_legacy_db(tmp_path / "legacy.sqlite")


def test_import_converts_and_reports(legacy_db, tmp_path):
    target = tmp_path / "new.sqlite"
    report = import_legacy(legacy_db, target)

    drivers, clients = report.tables["drivers"], report.tables["clients"]
    invoices, trips = report.tables["invoices"], report.tables["trips"]
    assert (drivers.read, drivers.imported) == (4, 3)
    assert (clients.read, clients.imported) == (3, 2)
    assert (invoices.read, invoices.imported) == (2, 1)
    assert (trips.read, trips.imported) == (3, 1)
    assert report.tables["municipalities"].imported == 5

    assert any("12345678A" in note for note in drivers.skipped)
    assert any("sin fecha de alta" in note for note in drivers.warnings)
    assert any("Malaga/Malaga → Málaga/Málaga" in note for note in drivers.fixed)
    assert any("345689012.0 → 345689012" in note for note in drivers.fixed)
    assert any("Bad Phone" in note or "53953216T" in note for note in clients.skipped)
    assert any("factura 9 no existe" in note for note in trips.skipped)
    assert any("Castejón" in note for note in trips.skipped)
    assert "descartado" in str(report) and "aviso" in str(report)

    conn = connect(target)
    driver = DriverRepository(conn).get(7)
    assert driver.hired_on is None
    assert driver.left_on == date(2023, 12, 18)
    assert driver.salary == Decimal("30000.00")
    assert DriverRepository(conn).get(38).salary == Decimal("28000.00")
    assert DriverRepository(conn).get(42).municipality == "Málaga"
    assert ClientRepository(conn).get(43).province == "Pontevedra"  # trailing space removed
    assert ClientRepository(conn).get(45).left_on == date(2023, 12, 11)
    invoice = InvoiceRepository(conn).get(1)
    assert invoice.issued_on == date(2023, 12, 26)
    assert invoice.driver_id == 7
    assert [(t.id, t.km, t.rate) for t in invoice.trips] == [(1, 10, Decimal("0.40"))]
    conn.close()


def test_does_not_overwrite_by_default(legacy_db, tmp_path):
    target = tmp_path / "new.sqlite"
    target.write_text("keep me")
    with pytest.raises(FileExistsError):
        import_legacy(legacy_db, target)
    assert target.read_text() == "keep me"
    import_legacy(legacy_db, target, overwrite=True)
    assert connect(target).execute("SELECT count(*) FROM drivers").fetchone()[0] == 3


def test_missing_legacy_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        import_legacy(tmp_path / "nope.sqlite", tmp_path / "new.sqlite")


def test_legacy_file_is_not_modified(legacy_db, tmp_path):
    before = legacy_db.read_bytes()
    import_legacy(legacy_db, tmp_path / "new.sqlite")
    assert legacy_db.read_bytes() == before


def test_cli(legacy_db, tmp_path, capsys):
    target = tmp_path / "new.sqlite"
    assert main([str(legacy_db), str(target)]) == 0
    assert "drivers: 4 leídos, 3 importados" in capsys.readouterr().out
    assert main([str(legacy_db), str(target)]) == 1
    assert "already exists" in capsys.readouterr().err
    assert main([str(legacy_db), str(target), "--overwrite"]) == 0


@pytest.mark.skipif(not REAL_LEGACY_DB.exists(), reason="legacy bbdd.sqlite not present")
def test_real_legacy_database(tmp_path):
    """The app's actual data: every record survives except the orphan trip (bug D4)."""
    report = import_legacy(REAL_LEGACY_DB, tmp_path / "new.sqlite")
    imported = {name: table.imported for name, table in report.tables.items()}
    assert imported == {
        "provinces": 52,
        "municipalities": 8116,
        "drivers": 19,
        "clients": 32,
        "invoices": 6,
        "trips": 31,
    }
    assert report.tables["trips"].skipped == ["viaje 41: la factura 9 no existe (bug D4)"]
    assert all(not table.skipped for name, table in report.tables.items() if name != "trips")
