import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from carteis.data import migrations
from carteis.data.converters import cents_to_money, date_from_db, date_to_db, money_to_cents
from carteis.data.database import connect, transaction, translate_integrity_errors
from carteis.domain.errors import DuplicateError, NotFoundError


def test_foreign_keys_are_enforced(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO municipalities (id, province_id, name) VALUES (99, 99, 'X')")


def test_transaction_commits(conn):
    with transaction(conn):
        conn.execute("INSERT INTO provinces (id, name) VALUES (10, 'Lugo')")
    assert not conn.in_transaction
    assert conn.execute("SELECT name FROM provinces WHERE id = 10").fetchone()[0] == "Lugo"


def test_transaction_rolls_back_on_error(conn):
    with pytest.raises(RuntimeError), transaction(conn):
        conn.execute("INSERT INTO provinces (id, name) VALUES (10, 'Lugo')")
        raise RuntimeError("boom")
    assert not conn.in_transaction
    assert conn.execute("SELECT count(*) FROM provinces WHERE id = 10").fetchone()[0] == 0


def test_nested_transaction_joins_outer(conn):
    with pytest.raises(RuntimeError), transaction(conn):
        conn.execute("INSERT INTO provinces (id, name) VALUES (10, 'Lugo')")
        with transaction(conn):
            conn.execute("INSERT INTO provinces (id, name) VALUES (11, 'Ourense')")
        raise RuntimeError("boom")
    assert conn.execute("SELECT count(*) FROM provinces WHERE id >= 10").fetchone()[0] == 0


def test_integrity_errors_are_translated(conn):
    with pytest.raises(DuplicateError, match="repetida"), translate_integrity_errors("repetida"):
        conn.execute("INSERT INTO provinces (id, name) VALUES (10, 'Vigo'), (11, 'Vigo')")
    with pytest.raises(NotFoundError), translate_integrity_errors("x"):
        conn.execute("INSERT INTO municipalities (id, province_id, name) VALUES (99, 99, 'X')")
    with pytest.raises(sqlite3.IntegrityError), translate_integrity_errors("x"):
        conn.execute("INSERT INTO provinces (id, name) VALUES (12, NULL)")  # NOT NULL


def test_migrate_is_idempotent(conn):
    version = migrations.current_version(conn)
    assert version == migrations.available()[-1][0]
    assert migrations.migrate(conn) == version


def test_failed_migration_rolls_back(monkeypatch):
    conn = connect(":memory:")
    monkeypatch.setattr(
        migrations, "available", lambda: [(1, "CREATE TABLE ok (id INTEGER); SELECT * FROM nope;")]
    )
    with pytest.raises(sqlite3.OperationalError):
        migrations.migrate(conn)
    assert migrations.current_version(conn) == 0
    assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name = 'ok'").fetchone()[0] == 0


def test_date_conversion():
    assert date_to_db(date(2024, 2, 5)) == "2024-02-05"
    assert date_to_db(None) is None
    assert date_from_db("2024-02-05") == date(2024, 2, 5)
    assert date_from_db(None) is None


def test_money_conversion():
    assert money_to_cents(Decimal("1500.50")) == 150050
    assert money_to_cents(Decimal("0.2")) == 20
    assert cents_to_money(150050) == Decimal("1500.50")
    with pytest.raises(ValueError):
        money_to_cents(Decimal("0.333"))
