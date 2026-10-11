"""Builders for valid domain objects; override any field with keyword arguments."""

from datetime import date
from decimal import Decimal

from carteis.domain.models import Client, Driver
from carteis.domain.pricing import Location

VIGO = Location("Pontevedra", "Vigo")
CANGAS = Location("Pontevedra", "Cangas")
FERROL = Location("A Coruña", "Ferrol")


def make_driver(**overrides) -> Driver:
    fields = {
        "dni": "12345678Z",
        "surname": "Gómez",
        "name": "Ana",
        "address": "Rúa do Príncipe 1",
        "province": "Pontevedra",
        "municipality": "Vigo",
        "phone": "612345678",
        "salary": Decimal("1500.50"),
        "licenses": {"B", "A"},
        "hired_on": date(2021, 9, 15),
    }
    return Driver(**(fields | overrides))


def make_client(**overrides) -> Client:
    fields = {
        "dni": "53854586V",
        "company_name": "So Factive",
        "address": "Estrela 1",
        "province": "Pontevedra",
        "municipality": "Cangas",
        "phone": "619669207",
    }
    return Client(**(fields | overrides))
