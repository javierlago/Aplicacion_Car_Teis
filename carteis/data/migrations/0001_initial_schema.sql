-- Initial schema. Replaces the legacy Spanish tables (provincias, municipios, drivers,
-- listadoClientes, facturas, viajes); carteis.data.legacy_import copies their data here.
--
-- Conventions: dates are ISO 'YYYY-MM-DD' text, money is integer cents, a NULL left_on
-- means the record is active (soft delete).

CREATE TABLE provinces (
    id   INTEGER PRIMARY KEY,
    name TEXT    NOT NULL UNIQUE
);

CREATE TABLE municipalities (
    id          INTEGER PRIMARY KEY,
    province_id INTEGER NOT NULL REFERENCES provinces (id),
    name        TEXT    NOT NULL,
    UNIQUE (province_id, name)
);

CREATE TABLE drivers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dni             TEXT    NOT NULL UNIQUE,
    surname         TEXT    NOT NULL,
    name            TEXT    NOT NULL,
    address         TEXT    NOT NULL,
    municipality_id INTEGER NOT NULL REFERENCES municipalities (id),
    phone           TEXT    NOT NULL CHECK (length(phone) = 9),
    salary_cents    INTEGER NOT NULL CHECK (salary_cents >= 0),
    licenses        TEXT    NOT NULL CHECK (licenses <> ''),  -- e.g. 'A,B,C'
    hired_on        TEXT    CHECK (hired_on IS NULL OR hired_on = date(hired_on)),
    left_on         TEXT    CHECK (left_on IS NULL OR left_on = date(left_on)),
    CHECK (hired_on IS NULL OR left_on IS NULL OR left_on >= hired_on)
);

CREATE TABLE clients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dni             TEXT    NOT NULL UNIQUE,
    company_name    TEXT    NOT NULL,
    address         TEXT    NOT NULL,
    municipality_id INTEGER NOT NULL REFERENCES municipalities (id),
    phone           TEXT    NOT NULL CHECK (length(phone) = 9),
    left_on         TEXT    CHECK (left_on IS NULL OR left_on = date(left_on))
);

CREATE TABLE invoices (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,  -- invoice number, never reused
    client_dni TEXT    NOT NULL REFERENCES clients (dni) ON UPDATE CASCADE,
    driver_id  INTEGER NOT NULL REFERENCES drivers (id),
    issued_on  TEXT    NOT NULL CHECK (issued_on = date(issued_on))
);

CREATE INDEX invoices_client_dni ON invoices (client_dni);
CREATE INDEX invoices_driver_id ON invoices (driver_id);

CREATE TABLE trips (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id     INTEGER NOT NULL REFERENCES invoices (id) ON DELETE CASCADE,
    origin_id      INTEGER NOT NULL REFERENCES municipalities (id),
    destination_id INTEGER NOT NULL REFERENCES municipalities (id),
    km             INTEGER NOT NULL CHECK (km > 0),
    rate_cents     INTEGER NOT NULL CHECK (rate_cents > 0)  -- price per km when invoiced
);

CREATE INDEX trips_invoice_id ON trips (invoice_id);
