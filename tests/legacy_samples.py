"""A legacy-schema (Spanish) database for import and backup tests."""

import sqlite3
from pathlib import Path

# Same tables as the legacy bbdd.sqlite (constraints trimmed to what matters here).
LEGACY_SCHEMA = """
CREATE TABLE provincias (idprov INTEGER, provincia TEXT);
CREATE TABLE municipios (idprov INTEGER, municipio TEXT, idmuni INTEGER);
CREATE TABLE drivers (codigo INTEGER PRIMARY KEY, dnidri TEXT, altadri TEXT, apeldri TEXT,
    nombredri TEXT, direcciondri TEXT, provdri TEXT, munidri TEXT, movildri TEXT,
    salario TEXT, carnet NUMERIC, bajadri TEXT);
CREATE TABLE listadoClientes (codigo INTEGER PRIMARY KEY, dnicliente TEXT, razon TEXT,
    direccion TEXT, telefono NUMERIC, provCliente TEXT, muniCliente TEXT, bajaCliente TEXT);
CREATE TABLE facturas (numFactura INTEGER PRIMARY KEY, dniCliente TEXT, fechaFactura TEXT,
    idConductor TEXT);
CREATE TABLE viajes (idViaje INTEGER PRIMARY KEY, idFactura INTEGER, origen TEXT,
    destino TEXT, kms INTEGER, tarifa NUMERIC);
"""


def build_legacy_db(path: Path) -> Path:
    """Create a small legacy-schema database with the quirks found in the real data."""
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_SCHEMA)
    conn.executemany(
        "INSERT INTO provincias VALUES (?, ?)",
        [(1, "Pontevedra"), (2, "Navarra"), (3, "Zaragoza"), (4, "Málaga ")],
    )
    conn.executemany(
        "INSERT INTO municipios VALUES (?, ?, ?)",
        [
            (1, "Vigo", 1),
            (1, "Cangas", 2),
            (2, "Castejón", 3),
            (3, "Castejón", 4),
            (4, "Málaga", 5),
        ],
    )
    conn.executemany(
        "INSERT INTO drivers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                7,
                "00000000T",
                "",
                "Perez",
                "Jose",
                "Urzaiz 2",
                "Pontevedra",
                "Vigo",
                "666123488",
                "30000,00 €",
                "A-B-C-D",
                "18/12/2023",
            ),
            (
                38,
                "65448835N",
                "31/12/2022",
                "López",
                "Jennifer",
                "Vieja 11",
                "Pontevedra",
                "Cangas",
                "722568945",
                "28.000,00 €",
                "A",
                "",
            ),
            (
                42,
                "45678901G",
                "09/12/2022",
                "Martinez",
                "Sergio",
                "Paz 1",
                "Malaga",
                "Malaga",
                "345689012.0",
                "40000.00",
                "C",
                "",
            ),
            (
                50,
                "12345678A",
                "01/01/2023",
                "Bad",
                "Dni",
                "x",
                "Pontevedra",
                "Vigo",
                "612345678",
                "1000",
                "B",
                "",
            ),
        ],
    )
    conn.executemany(
        "INSERT INTO listadoClientes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (43, "53854586V", "So Factive", "Estrela", 619669207, "Pontevedra ", "Vigo", ""),
            (
                45,
                "53914923W",
                "Finance Api",
                "Ourense 38",
                659248290,
                "Pontevedra",
                "Cangas",
                "11/12/2023",
            ),
            (46, "53953216T", "Bad Phone", "x", 12345, "Pontevedra", "Vigo", ""),
        ],
    )
    conn.executemany(
        "INSERT INTO facturas VALUES (?, ?, ?, ?)",
        [(1, "53854586V", "26/12/2023", "7"), (2, "99999999R", "27/12/2023", "7")],
    )
    conn.executemany(
        "INSERT INTO viajes VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, 1, "Vigo", "Cangas", 10, 0.4),
            (2, 9, "Vigo", "Vigo", 5, 0.2),  # orphan: invoice 9 was deleted
            (3, 1, "Castejón", "Vigo", 5, 0.8),  # ambiguous municipality
        ],
    )
    conn.commit()
    conn.close()
    return path
