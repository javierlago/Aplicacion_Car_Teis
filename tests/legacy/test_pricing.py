"""Characterization tests for the legacy fare and invoice-total calculation."""

from unittest.mock import MagicMock

import pytest

from Facturas.facturacion import Facturacion


def _set_route(ui, prov_from, prov_to, town_from, town_to):
    ui.cmb_provincia_origen.currentText.return_value = prov_from
    ui.cmb_provincia_destino.currentText.return_value = prov_to
    ui.cmb_localidad_origen.currentText.return_value = town_from
    ui.cmb_localidad_destino.currentText.return_value = town_to


@pytest.mark.parametrize(
    "route, rate, radio",
    [
        (("Pontevedra", "Pontevedra", "Vigo", "Vigo"), 0.2, "rbt_tarifa_local"),
        (("Pontevedra", "Pontevedra", "Vigo", "Cangas"), 0.4, "rbt_tarifa_provincia"),
        (("Pontevedra", "A Coruña", "Vigo", "Ferrol"), 0.8, "rbt_tarifa_nacional"),
        # Different province wins even if the town names match.
        (("Pontevedra", "A Coruña", "Vigo", "Vigo"), 0.8, "rbt_tarifa_nacional"),
    ],
)
def test_fare_by_route(fake_ui, route, rate, radio):
    _set_route(fake_ui, *route)
    assert Facturacion.calcular_tarifa() == rate
    getattr(fake_ui, radio).setChecked.assert_called_with(True)


def test_empty_route_counts_as_local(fake_ui):
    _set_route(fake_ui, "", "", "", "")
    assert Facturacion.calcular_tarifa() == 0.2


def _fake_trip_table(line_totals):
    table = MagicMock()
    table.rowCount.return_value = len(line_totals)
    table.item.side_effect = lambda row, col: MagicMock(
        text=MagicMock(return_value=line_totals[row])
    )
    return table


def test_invoice_subtotal_sums_the_total_column():
    assert Facturacion.calculo_factura_de_viaje(_fake_trip_table(["10.0", "2.5"])) == 12.5


def test_invoice_subtotal_uses_float_arithmetic():
    # Money is summed as float: 0.1 + 0.2 is not exactly 0.3. Phase 1 moves this to Decimal.
    subtotal = Facturacion.calculo_factura_de_viaje(_fake_trip_table(["0.1", "0.2"]))
    assert subtotal != 0.3
    assert round(subtotal, 2) == 0.3


def test_invoice_subtotal_of_empty_table_is_zero():
    assert Facturacion.calculo_factura_de_viaje(_fake_trip_table([])) == 0
