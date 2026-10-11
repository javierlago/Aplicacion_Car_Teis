"""Check that the new domain code agrees with the legacy code it replaces."""

import random
import string
from decimal import Decimal

import pytest

import drivers
from carteis.domain.pricing import Location, Tariff
from carteis.domain.validators import is_valid_dni
from Facturas.facturacion import Facturacion

_rng = random.Random(20261011)


def _random_dni_candidates(count):
    letters = string.ascii_uppercase
    for _ in range(count):
        digits = "".join(_rng.choices(string.digits, k=8))
        if _rng.random() < 0.3:
            digits = _rng.choice("XYZ") + digits[1:]
        yield digits + _rng.choice(letters)


DNI_SAMPLE = list(_random_dni_candidates(2000))


def test_sample_contains_both_outcomes():
    valid = sum(is_valid_dni(dni) for dni in DNI_SAMPLE)
    assert 0 < valid < len(DNI_SAMPLE)


@pytest.mark.parametrize("chunk", range(10))
def test_dni_validation_matches_legacy(fake_ui, chunk):
    for dni in DNI_SAMPLE[chunk::10]:
        assert is_valid_dni(dni) == bool(drivers.Drivers.validar_dni(dni)), dni


ROUTES = [
    ("Pontevedra", "Vigo", "Pontevedra", "Vigo"),
    ("Pontevedra", "Vigo", "Pontevedra", "Cangas"),
    ("Pontevedra", "Vigo", "A Coruña", "Ferrol"),
    ("Pontevedra", "Vigo", "A Coruña", "Vigo"),
    ("Álava", "Alegría-Dulantzi", "Albacete", "Alatoz"),
]


@pytest.mark.parametrize("prov_from, town_from, prov_to, town_to", ROUTES)
def test_fare_matches_legacy(fake_ui, prov_from, town_from, prov_to, town_to):
    fake_ui.cmb_provincia_origen.currentText.return_value = prov_from
    fake_ui.cmb_provincia_destino.currentText.return_value = prov_to
    fake_ui.cmb_localidad_origen.currentText.return_value = town_from
    fake_ui.cmb_localidad_destino.currentText.return_value = town_to

    new_rate = Tariff().rate_between(Location(prov_from, town_from), Location(prov_to, town_to))
    assert new_rate == Decimal(str(Facturacion.calcular_tarifa()))
