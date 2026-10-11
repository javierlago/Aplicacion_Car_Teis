# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

CarTeis is a desktop app (Python + PyQt6 + SQLite + reportlab) for managing a taxi company: drivers (conductores), clients, and invoicing (facturas with trip lines / viajes). **Code identifiers are in English; everything the user sees (UI text, error messages, reports) is in Spanish.**

## History

The app was fully refactored from a student project on the `refactor` branch. [refactor_plan/](refactor_plan/) holds the audit of the original code (`01_auditoria.md`), the phased plan with each phase's results and deliberate behaviour changes (`02_plan.md`) and the manual regression checklist (`03_checklist_manual.md`). User-facing docs live in `docs/` (Sphinx) and `README.md`.

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
.venv/Scripts/pyinstaller carteis.spec           # dist/CarTeis.exe (extra "build")
.venv/Scripts/sphinx-build -W docs docs/_build/html   # docs (extra "docs"); must stay warning-free
```

## Architecture (`carteis/`)

Layers depend in one direction: `ui → services → domain ← data`.

- **`domain/`** — pure Python, no Qt or SQL. Dataclass entities that validate and normalize themselves on construction (`models.py`); one implementation of each validator (`validators.py`); fares and totals with `Decimal` rounded half-up to cents (`pricing.py`, `money.py`); locale-free Spanish date/money formatting (`formatting.py`). Problems are raised as `DomainError` subclasses (`errors.py`) whose message is shown to the user as-is; `ValidationError.field` names the offending field. Fares and VAT live in `carteis/config.py`.
- **`data/`** — stdlib `sqlite3`. `database.connect()` enables foreign keys and autocommit; multi-statement writes use the nestable `transaction()` context manager, and repositories never commit on their own. Schema changes are new `migrations/NNNN_name.sql` files (version in `PRAGMA user_version`; never edit an applied one). Schema conventions: English names, ISO date text, money as integer cents, locations as `municipality_id` FKs (municipality names repeat across provinces, so `Trip` stores full `Location`s). Repositories map rows to/from domain models and translate UNIQUE/FK violations into `DuplicateError`/`NotFoundError`. `legacy_import.py` converts the legacy Spanish-schema DB.
- **`services/`** — the use cases the UI calls: `DriverService`/`ClientService` (share `_PersonService`), `InvoicingService` (fares always come from the `Tariff`, never from the caller), `BackupService` (SQLite online backup API both ways; validates archives, converts legacy backups), `SpreadsheetService` (`.xlsx` via openpyxl, columns matched by normalized header), `ReportService` (writes PDFs under an output dir passed in by the UI). They take a `sqlite3.Connection` plus injectable `today`/`now` callables.
- **`reports/`** — reportlab, no Qt or DB: plain functions of domain objects. `pdf.Report` draws the shared page frame (company header from `config.COMPANY`, logo, footer) on every page; `pdf.Table` repeats its header across page breaks and shortens overflowing text with `fit()`. Coordinates are A4 points matching the legacy layout.
- **`ui/`** — `main_window.py` builds the window and wires menus/toolbar; `tabs/` has one controller per tab. Controllers never open dialogs directly: all modal interaction (messages, confirmations, file pickers, calendar, report choice, opening generated PDFs) goes through `prompts.Prompts`, injected via `MainWindow(prompts_factory=...)`. Slots that can fail are wrapped with `forms.user_action`, which shows the `DomainError`, focuses `field_widgets[error.field]`, and passes the method only as many signal arguments as it declares. Tables are `QTableView`s with `table_models.RecordTableModel`. `ui/generated/` is pyuic output — never edit it; edit `resources/ui/*.ui` (Qt Designer) and run `tools/build_ui.py`, which also rewrites image paths to the `img:` search path.
- **Start-up** (`app.py`, `paths.py`): sets the style sheet and `img:` search path, rotating log file and an exception hook (logs and reports unexpected errors instead of PyQt aborting), and creates the user's DB from `resources/seed.sqlite` on first run. Nothing depends on the working directory.

**Look and layout:** colours live once in `carteis/ui/theme.py` (`COLORS`); `resources/styles.qss` writes them as `@token` and `theme.style_sheet()` substitutes them (unknown tokens raise; comments are stripped first). The app runs the Fusion style with `theme.palette()` and the bundled Inter font, so nothing depends on the Windows theme or installed fonts. Widgets share a look through a dynamic `role` property in the `.ui` (`field`, `primary`, `outline`, `danger`, `icon`, `highlight`, `total`, `title`, `table`, `panel`, `fare`); mind specificity when adding rules (an id selector beats a role selector). Forms are `QGridLayout`s (label and field share a row, 28 px minimum row height); each tab's card and tables expand to the same 1160 px maximum with side spacers of preferred size 0, and `test_cards_and_tables_share_their_edges` guards that. QHeaderView ignores style-sheet padding when sizing sections, so `RecordTableModel.set_header_metrics` supplies header widths via `SizeHintRole`; per-column alignment comes from `Column.align`. Lucide icons are fetched and coloured with `tools/fetch_icons.py`.

## Tests

`tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` and provides `conn`, an in-memory migrated DB with a few locations (note "Castejón" exists in two provinces). Builders live in `tests/factories.py`, a small synthetic legacy DB in `tests/legacy_samples.py`, and the original app's real database in `tests/fixtures/legacy_bbdd.sqlite` (used to test converting/restoring legacy backups). `tests/ui/conftest.py` provides `window` (a real `MainWindow` with `FakePrompts`, which records messages and answers from queues: `confirm_answers`, `files`, `dates`, `choices`; generated PDFs land in `opened`) and makes any real `QMessageBox`/`QDialog.exec()` fail the test instead of hanging. Report tests read PDFs back with pypdf; `extract_text()` puts each drawn string on its own line, so tests join on whitespace before matching.
