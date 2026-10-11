"""Characterization tests for the legacy validators.

They pin down what the current code does (bugs included) so the rewritten
``domain.validators`` module can be checked against it in phase 1.
"""

import pytest

import cliente
import drivers

VALID_DNIS = [
    "12345678Z",
    "00000000T",
    "12345678z",  # lowercase is accepted
    "X1234567L",  # NIE starting with X
    "Y1234567X",  # NIE starting with Y
    "Z1234567R",  # NIE starting with Z
]

INVALID_DNIS = [
    "12345678A",  # wrong control letter
    "1234567Z",  # too short
    "123456789Z",  # too long
    "",
    "1234A678Z",  # letter in the middle
    "W1234567L",  # unsupported NIE prefix
]


@pytest.mark.parametrize("dni", VALID_DNIS)
def test_driver_dni_valid(fake_ui, dni):
    assert drivers.Drivers.validar_dni(dni) is True


@pytest.mark.parametrize("dni", INVALID_DNIS)
def test_driver_dni_invalid_returns_none_and_clears_field(fake_ui, dni):
    # Current behaviour: returns None (not False) and empties the DNI box.
    assert drivers.Drivers.validar_dni(dni) is None
    fake_ui.txtDni.setText.assert_called_with("")


@pytest.mark.parametrize("dni", VALID_DNIS)
def test_client_dni_valid(fake_ui, dni):
    assert cliente.Cliente.validar_dni(dni) is True


@pytest.mark.parametrize("dni", INVALID_DNIS)
def test_client_dni_invalid_returns_none_and_clears_field(fake_ui, dni):
    assert cliente.Cliente.validar_dni(dni) is None
    fake_ui.txtDni_3.setText.assert_called_with("")


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1500", True),
        ("1500.5", True),
        ("1500.50", True),
        ("0", True),
        ("1500.505", False),  # more than two decimals
        ("1500,50", False),  # comma is converted to a dot by the caller, not here
        ("-10", False),
        ("abc", False),
        ("", False),
    ],
)
def test_salary_number_format(value, expected):
    assert drivers.Drivers.validar_numero(value) is expected


@pytest.mark.parametrize(
    "phone, valid",
    [("612345678", True), ("61234567", False), ("6123456789", False), ("61234567a", False)],
)
def test_driver_phone(fake_ui, messages, phone, valid):
    fake_ui.txtMovil.text.return_value = phone
    drivers.Drivers.validar_tlf()
    if valid:
        fake_ui.txtMovil.setText.assert_called_with(phone)
        messages.warning.assert_not_called()
    else:
        fake_ui.txtMovil.setText.assert_called_with("")
        messages.warning.assert_called_once()


def test_required_fields_ignores_last_item():
    # Bug F10: the last element is never checked.
    assert drivers.Drivers.validar_datos(["a", "b", ""]) is True
    assert drivers.Drivers.validar_datos(["a", "", "c"]) is False
    assert drivers.Drivers.validar_datos(["a", "   ", "c"]) is False
    assert cliente.Cliente.validar_datos(["a", "b", ""]) is True
