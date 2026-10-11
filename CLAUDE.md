# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

CarTeis is a Windows desktop app (Python + PyQt6 + SQLite) for managing a taxi company: drivers (conductores), clients, and invoicing (facturas with trip lines / viajes). The legacy code, identifiers and UI text are in Spanish. Startup calls `locale.setlocale(..., 'es_ES.UTF-8')`, which must be available on the machine or the app crashes at import.

## Refactor in progress

The app is being fully refactored on the `refactor` branch, following [refactor_plan/02_plan.md](refactor_plan/02_plan.md) (audit in `01_auditoria.md`, manual regression checklist in `03_checklist_manual.md`). Key decisions recorded there: stack stays PyQt6 + SQLite + reportlab; new code goes in a `carteis/` package with `domain/`, `data/`, `services/`, `reports/`, `ui/` layers; **new code identifiers are in English, user-facing text stays in Spanish**; `sqlite3` instead of `QtSql`; `.xlsx` via `openpyxl`; ISO dates and numeric salary after the schema migration. Do not start a phase without the user's explicit approval. The legacy modules described below remain until phase 4 replaces them — don't lint-fix or reformat them.

## Commands

All commands must be run from the repo root — the DB (`bbdd.sqlite`) and output folders (`informes\`, `Facturacion\`) are opened via relative paths.

```sh
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"   # setup (deps only; no package yet)
.venv/Scripts/python main.py                     # run the app
.venv/Scripts/python -m pytest                   # all tests (Qt runs offscreen)
.venv/Scripts/python -m pytest tests/legacy/test_validators.py::test_driver_dni_valid   # single test
.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check tests   # lint (legacy has ~411 known warnings)
pyuic6 -x templates/MainWindow.ui -o MainWindow.py   # regenerate a UI module after editing a .ui in Qt Designer
pyinstaller main.spec                            # build dist/main.exe (bundles bbdd.sqlite, icon IconTaxi.ico)
cd docs && make html                             # Sphinx docs (autodoc); docs/conf.py has a hardcoded sys.path from another machine
```

New package (`pip install -e .` installs only `carteis*`): `carteis/config.py` holds fares and VAT; `carteis/domain/` is pure Python (no Qt, no SQL) — dataclass entities that validate themselves on construction (`models.py`), a single implementation of each validator (`validators.py`, raising `ValidationError` with Spanish user-facing messages and a `field`), fares/totals with `Decimal` rounded half-up to cents (`pricing.py`, `money.py`), and locale-free Spanish date/money formatting (`formatting.py`). Behaviour changes vs. legacy are listed under phase 1 in `refactor_plan/02_plan.md`.

Tests: `tests/domain/` covers the new package (keep it at 100% with `pytest --cov`). `tests/legacy/` are characterization tests that pin current behaviour (bugs included) of the legacy code, plus `test_parity.py` checking new code agrees with legacy. `tests/legacy/conftest.py` provides `fake_ui` (mocks the global `var.ui`) and `messages` (captures `Ventanas` pop-ups), and makes any `QMessageBox.exec()` fail the test instead of blocking forever. Running the app writes to the tracked `bbdd.sqlite`; restore it with `git checkout bbdd.sqlite` (a pre-refactor copy lives in the git-ignored `backups/`).

## Architecture

**UI layer is generated.** `MainWindow.py`, `AcercaDeWindow.py`, `VentanaSalir.py`, `WindowCalendar.py` are `pyuic6` output from `templates/*.ui` — never hand-edit them; change the `.ui` and regenerate. `windowaux.py` wraps the generated dialogs in `QDialog` subclasses and wires their buttons.

**Global state lives in `var.py`.** `var.ui` is the main `Ui_MainWindow` instance; every module reaches widgets directly through it (e.g. `var.ui.txtDni.text()`). Other globals: `var.calendar`, `var.acercade`, `var.ventana_salir`, `var.dlg_abrir`, `var.bbdd` (DB path), `var.report` (current reportlab canvas). Modules don't pass widgets around — they read/write `var`.

**`main.py` is the composition root.** `Main.__init__` builds the UI, opens the DB, populates combos/tables, and contains *all* signal→slot wiring. When adding a feature, connect its signals here.

**Handlers are static-style methods on classes**, defined without `@staticmethod` and connected directly as slots (often taking a dummy `self`/`self=None`). Follow this convention rather than instantiating classes:
- `drivers.Drivers`, `cliente.Cliente` — form read/validate (DNI, phone, salary), load row from table into form.
- `conexion.Conexion` — DB connection (`QSqlDatabase` QSQLITE, global default connection) plus most SQL for drivers/clients/provinces and table refreshes (`mostrardrivers`, `mostrarclientes`, `cargar_facturas`).
- `Facturas/facturacion.py` (form/table logic, fare calculation), `Facturas/facturacion_repository.py` (invoice/trip SQL), `Facturas/facturacion_informes.py` (invoice PDF).
- `eventos.Eventos` — misc UI events: dialogs, clear forms, table resizing, status bar, zip backup/restore of `bbdd.sqlite`, XLS import/export.
- `informes.informes` — reportlab PDF listings written to `informes\` and opened with `os.startfile`; invoice PDFs go to `Facturacion\`.
- `Ventanas.Ventanas` — shared info/warning message boxes.

Modules import each other circularly (`conexion` ↔ `cliente`/`drivers`/`Facturas`); keep imports at module level as module references (`import conexion` then `conexion.Conexion.x()`), not `from x import y`, to avoid breaking import order.

**Database** (`bbdd.sqlite`, queried via `QtSql.QSqlQuery` with named `bindValue` params): `drivers`, `listadoClientes`, `facturas`, `viajes` (FK `idFactura` → `facturas.numFactura`, on delete cascade), `provincias`/`municipios` (lookup data, CSV source in `DatosCSV/`). Deletion of drivers/clients is a soft delete — a `baja*` date column is set; the radio-button groups filter active/inactive/all. Dates are stored as `dd/mm/YYYY` text.

`styles/styles.qss` exists but is not loaded by the code.
