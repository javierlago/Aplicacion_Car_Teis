# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

CarTeis is a desktop app (Python + PyQt6 + SQLite + reportlab) for managing a taxi company: drivers (conductores), clients, and invoicing (facturas with trip lines / viajes). **Code identifiers are in English; everything the user sees (UI text, error messages, reports) is in Spanish.**

## Refactor in progress

The app is being fully refactored on the `refactor` branch, following [refactor_plan/02_plan.md](refactor_plan/02_plan.md) (audit in `01_auditoria.md`, manual regression checklist in `03_checklist_manual.md`). Each phase records its results and deliberate behaviour changes there. Do not start a phase without the user's explicit approval. Phases 0–5 are done and the legacy app has been deleted; phase 6 (packaging and docs) remains — `main.spec` and `docs/` still point at the deleted legacy modules.

## Commands

```sh
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"   # setup
.venv/Scripts/python -m carteis                  # run the new app (DB in %APPDATA%/CarTeis/CarTeis)
CARTEIS_DB=/path/copy.sqlite .venv/Scripts/python -m carteis   # run it on another database file
.venv/Scripts/python -m pytest                   # all tests (Qt runs offscreen)
.venv/Scripts/python -m pytest --cov             # coverage; keep carteis/ at 100%
.venv/Scripts/python -m pytest tests/ui/test_invoicing_tab.py::test_add_trip   # single test
.venv/Scripts/ruff check carteis tests tools && .venv/Scripts/ruff format --check carteis tests tools
.venv/Scripts/python tools/build_ui.py           # regenerate carteis/ui/generated after editing resources/ui/*.ui
.venv/Scripts/python -m carteis.data.legacy_import tests/fixtures/legacy_bbdd.sqlite resources/seed.sqlite --overwrite   # rebuild seed DB
```

## Architecture (`carteis/`)

Layers depend in one direction: `ui → services → domain ← data`.

- **`domain/`** — pure Python, no Qt or SQL. Dataclass entities that validate and normalize themselves on construction (`models.py`); one implementation of each validator (`validators.py`); fares and totals with `Decimal` rounded half-up to cents (`pricing.py`, `money.py`); locale-free Spanish date/money formatting (`formatting.py`). Problems are raised as `DomainError` subclasses (`errors.py`) whose message is shown to the user as-is; `ValidationError.field` names the offending field. Fares and VAT live in `carteis/config.py`.
- **`data/`** — stdlib `sqlite3`. `database.connect()` enables foreign keys and autocommit; multi-statement writes use the nestable `transaction()` context manager, and repositories never commit on their own. Schema changes are new `migrations/NNNN_name.sql` files (version in `PRAGMA user_version`; never edit an applied one). Schema conventions: English names, ISO date text, money as integer cents, locations as `municipality_id` FKs (municipality names repeat across provinces, so `Trip` stores full `Location`s). Repositories map rows to/from domain models and translate UNIQUE/FK violations into `DuplicateError`/`NotFoundError`. `legacy_import.py` converts the legacy Spanish-schema DB.
- **`services/`** — the use cases the UI calls: `DriverService`/`ClientService` (share `_PersonService`), `InvoicingService` (fares always come from the `Tariff`, never from the caller), `BackupService` (SQLite online backup API both ways; validates archives, converts legacy backups), `SpreadsheetService` (`.xlsx` via openpyxl, columns matched by normalized header), `ReportService` (writes PDFs under an output dir passed in by the UI). They take a `sqlite3.Connection` plus injectable `today`/`now` callables.
- **`reports/`** — reportlab, no Qt or DB: plain functions of domain objects. `pdf.Report` draws the shared page frame (company header from `config.COMPANY`, logo, footer) on every page; `pdf.Table` repeats its header across page breaks and shortens overflowing text with `fit()`. Coordinates are A4 points matching the legacy layout.
- **`ui/`** — `main_window.py` builds the window and wires menus/toolbar; `tabs/` has one controller per tab. Controllers never open dialogs directly: all modal interaction (messages, confirmations, file pickers, calendar, report choice, opening generated PDFs) goes through `prompts.Prompts`, injected via `MainWindow(prompts_factory=...)`. Slots that can fail are wrapped with `forms.user_action`, which shows the `DomainError` and focuses `field_widgets[error.field]`. Tables are `QTableView`s with `table_models.RecordTableModel`. `ui/generated/` is pyuic output — never edit it; edit `resources/ui/*.ui` (Qt Designer) and run `tools/build_ui.py`, which also rewrites image paths to the `img:` search path.
- **Start-up** (`app.py`, `paths.py`): sets the style sheet and `img:` search path, rotating log file and an exception hook (logs and reports unexpected errors instead of PyQt aborting), and creates the user's DB from `resources/seed.sqlite` on first run. Nothing depends on the working directory.

**Styling:** all style is in `resources/styles.qss`. Widgets that share a look carry a dynamic `role` property in the `.ui` (`field`, `primary`, `secondary`, `highlight`, `total`, `title`, `table`, `panel`…). Rules written as `X, X *` reproduce old selector-less styles that also applied to children; mind specificity when adding rules (an id selector beats a role selector).

## Tests

`tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` and provides `conn`, an in-memory migrated DB with a few locations (note "Castejón" exists in two provinces). Builders live in `tests/factories.py`, a small synthetic legacy DB in `tests/legacy_samples.py`, and the original app's real database in `tests/fixtures/legacy_bbdd.sqlite` (used to test converting/restoring legacy backups). `tests/ui/conftest.py` provides `window` (a real `MainWindow` with `FakePrompts`, which records messages and answers from queues: `confirm_answers`, `files`, `dates`, `choices`; generated PDFs land in `opened`) and makes any real `QMessageBox`/`QDialog.exec()` fail the test instead of hanging. Report tests read PDFs back with pypdf; `extract_text()` puts each drawn string on its own line, so tests join on whitespace before matching.
