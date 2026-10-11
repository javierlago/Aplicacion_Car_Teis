"""Copy the data of a legacy CarTeis database (Spanish schema) into a new-schema database.

Usage::

    python -m carteis.data.legacy_import bbdd.sqlite resources/seed.sqlite [--overwrite]

Every record goes through the domain models, so anything invalid is reported instead of
copied. The legacy database is opened read-only and never modified.
"""

import argparse
import sqlite3
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from carteis.data.database import connect, transaction
from carteis.data.migrations import migrate
from carteis.data.repositories import (
    ClientRepository,
    DriverRepository,
    InvoiceRepository,
    LocationRepository,
)
from carteis.domain.errors import DomainError
from carteis.domain.formatting import parse_date
from carteis.domain.models import Client, Driver, Invoice, Trip
from carteis.domain.pricing import Location
from carteis.domain.validators import parse_money

# Locations typed by hand in the legacy data that don't match the reference tables.
LOCATION_FIXES: dict[tuple[str, str], tuple[str, str]] = {
    ("Malaga", "Malaga"): ("Málaga", "Málaga"),
    ("Gerona", "Olot"): ("Girona", "Olot"),
    ("Mallorca", "Palma de Mallorca"): ("Illes Balears", "Palma"),
    ("Bilbao", "Baracaldo"): ("Vizcaya", "Barakaldo"),
    ("Santander", "Santillana del Mar"): ("Cantabria", "Santillana del Mar"),
}


@dataclass
class TableReport:
    read: int = 0
    imported: int = 0
    skipped: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ImportReport:
    tables: dict[str, TableReport] = field(default_factory=dict)

    def table(self, name: str) -> TableReport:
        return self.tables.setdefault(name, TableReport())

    def __str__(self) -> str:
        lines = []
        for name, table in self.tables.items():
            lines.append(f"{name}: {table.read} leídos, {table.imported} importados")
            lines += [f"  corregido: {note}" for note in table.fixed]
            lines += [f"  aviso: {note}" for note in table.warnings]
            lines += [f"  descartado: {note}" for note in table.skipped]
        return "\n".join(lines)


def import_legacy(legacy_path: Path, target_path: Path, *, overwrite: bool = False) -> ImportReport:
    if not legacy_path.is_file():
        raise FileNotFoundError(legacy_path)
    if target_path.exists():
        if not overwrite:
            raise FileExistsError(f"{target_path} already exists (use overwrite=True)")
        target_path.unlink()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    report = ImportReport()
    source = sqlite3.connect(f"file:{legacy_path.as_posix()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    target = connect(target_path)
    try:
        migrate(target)
        with transaction(target):
            _copy_locations(source, target, report)
            _copy_drivers(source, target, report)
            _copy_clients(source, target, report)
            _copy_invoices_and_trips(source, target, report)
        target.execute("VACUUM")
    finally:
        source.close()
        target.close()
    return report


def _copy_locations(source, target, report: ImportReport) -> None:
    provinces = source.execute("SELECT idprov, provincia FROM provincias").fetchall()
    target.executemany(
        "INSERT INTO provinces (id, name) VALUES (?, ?)",
        [(row["idprov"], row["provincia"].strip()) for row in provinces],
    )
    report.table("provinces").read = report.table("provinces").imported = len(provinces)

    municipalities = source.execute("SELECT idmuni, idprov, municipio FROM municipios").fetchall()
    target.executemany(
        "INSERT INTO municipalities (id, province_id, name) VALUES (?, ?, ?)",
        [(row["idmuni"], row["idprov"], row["municipio"].strip()) for row in municipalities],
    )
    table = report.table("municipalities")
    table.read = table.imported = len(municipalities)


def _fix_location(province: str, municipality: str, table: TableReport, who: str) -> Location:
    key = (province.strip(), municipality.strip())
    if key in LOCATION_FIXES:
        fixed = LOCATION_FIXES[key]
        table.fixed.append(f"{who}: {key[0]}/{key[1]} → {fixed[0]}/{fixed[1]}")
        key = fixed
    return Location(*key)


def _optional_date(value: str | None):
    return parse_date(value) if value and value.strip() else None


def _copy_drivers(source, target, report: ImportReport) -> None:
    table = report.table("drivers")
    repo = DriverRepository(target)
    for row in source.execute("SELECT * FROM drivers ORDER BY codigo"):
        table.read += 1
        who = f"conductor {row['codigo']} ({row['dnidri']})"
        try:
            location = _fix_location(row["provdri"], row["munidri"], table, who)
            phone = row["movildri"]
            if phone.endswith(".0"):  # stored as a float by the legacy .xls import
                phone = phone.removesuffix(".0")
                table.fixed.append(f"{who}: teléfono {row['movildri']} → {phone}")
            hired_on = _optional_date(row["altadri"])
            if hired_on is None:
                table.warnings.append(f"{who}: sin fecha de alta (perdida por el bug D3)")
            repo.add(
                Driver(
                    id=row["codigo"],
                    dni=row["dnidri"],
                    surname=row["apeldri"],
                    name=row["nombredri"],
                    address=row["direcciondri"],
                    province=location.province,
                    municipality=location.municipality,
                    phone=phone,
                    salary=parse_money(row["salario"]),
                    licenses=frozenset(row["carnet"].split("-")),
                    hired_on=hired_on,
                    left_on=_optional_date(row["bajadri"]),
                )
            )
            table.imported += 1
        except DomainError as error:
            table.skipped.append(f"{who}: {error}")


def _copy_clients(source, target, report: ImportReport) -> None:
    table = report.table("clients")
    repo = ClientRepository(target)
    for row in source.execute("SELECT * FROM listadoClientes ORDER BY codigo"):
        table.read += 1
        who = f"cliente {row['codigo']} ({row['dnicliente']})"
        try:
            location = _fix_location(row["provCliente"], row["muniCliente"], table, who)
            repo.add(
                Client(
                    id=row["codigo"],
                    dni=row["dnicliente"],
                    company_name=row["razon"],
                    address=row["direccion"],
                    province=location.province,
                    municipality=location.municipality,
                    phone=str(row["telefono"]),
                    left_on=_optional_date(row["bajaCliente"]),
                )
            )
            table.imported += 1
        except DomainError as error:
            table.skipped.append(f"{who}: {error}")


def _copy_invoices_and_trips(source, target, report: ImportReport) -> None:
    invoices = report.table("invoices")
    repo = InvoiceRepository(target)
    imported_ids = set()
    for row in source.execute("SELECT * FROM facturas ORDER BY numFactura"):
        invoices.read += 1
        who = f"factura {row['numFactura']}"
        try:
            repo.add(
                Invoice(
                    id=row["numFactura"],
                    client_dni=row["dniCliente"],
                    driver_id=int(row["idConductor"]),
                    issued_on=parse_date(row["fechaFactura"]),
                )
            )
            imported_ids.add(row["numFactura"])
            invoices.imported += 1
        except DomainError as error:
            invoices.skipped.append(f"{who}: {error}")

    trips = report.table("trips")
    locations = LocationRepository(target)
    for row in source.execute("SELECT * FROM viajes ORDER BY idViaje"):
        trips.read += 1
        who = f"viaje {row['idViaje']}"
        if row["idFactura"] not in imported_ids:
            trips.skipped.append(f"{who}: la factura {row['idFactura']} no existe (bug D4)")
            continue
        try:
            repo.add_trip(
                row["idFactura"],
                Trip(
                    id=row["idViaje"],
                    origin=_resolve_municipality(locations, row["origen"]),
                    destination=_resolve_municipality(locations, row["destino"]),
                    km=row["kms"],
                    rate=Decimal(str(row["tarifa"])),
                ),
            )
            trips.imported += 1
        except DomainError as error:
            trips.skipped.append(f"{who}: {error}")


def _resolve_municipality(locations: LocationRepository, municipality: str) -> Location:
    """Legacy trips only stored the municipality name; find its province."""
    provinces = locations.provinces_of(municipality)
    if len(provinces) != 1:
        raise DomainError(
            f"no se puede deducir la provincia de «{municipality}» ({len(provinces)} coincidencias)"
        )
    return Location(provinces[0], municipality)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("legacy", type=Path, help="legacy database (e.g. bbdd.sqlite)")
    parser.add_argument("target", type=Path, help="new database to create")
    parser.add_argument("--overwrite", action="store_true", help="replace target if it exists")
    args = parser.parse_args(argv)
    try:
        report = import_legacy(args.legacy, args.target, overwrite=args.overwrite)
    except (FileNotFoundError, FileExistsError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
