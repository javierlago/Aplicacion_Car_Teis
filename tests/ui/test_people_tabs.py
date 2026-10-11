from datetime import date

import pytest

from carteis.services import ClientService, DriverService
from tests.factories import make_client, make_driver
from tests.ui.conftest import click_row, table_texts


def fill_driver_form(ui, **overrides):
    values = {
        "dni": "12345678Z",
        "surname": "gómez pérez",
        "name": "ana",
        "address": "Rúa do Príncipe 1",
        "province": "Pontevedra",
        "municipality": "Vigo",
        "phone": "612345678",
        "salary": "1500,5",
        "hired_on": "15/09/2021",
    } | overrides
    ui.txtDriverDni.setText(values["dni"])
    ui.txtDriverSurname.setText(values["surname"])
    ui.txtDriverSurname.editingFinished.emit()
    ui.txtDriverName.setText(values["name"])
    ui.txtDriverName.editingFinished.emit()
    ui.txtDriverAddress.setText(values["address"])
    ui.cmbDriverProvince.setCurrentText(values["province"])
    ui.cmbDriverMunicipality.setCurrentText(values["municipality"])
    ui.txtDriverPhone.setText(values["phone"])
    ui.txtDriverSalary.setText(values["salary"])
    ui.txtDriverSalary.editingFinished.emit()
    ui.txtDriverHiredOn.setText(values["hired_on"])
    ui.chkLicenseB.setChecked(True)


class TestDriversTab:
    def test_register(self, window, prompts, conn):
        ui = window.ui
        fill_driver_form(ui)
        assert ui.txtDriverSurname.text() == "Gómez Pérez"  # title case on leaving the box
        assert ui.txtDriverSalary.text() == "1.500,50 €"
        ui.btnDriverRegister.click()

        assert prompts.last == ("info", "Conductor Ana Gómez Pérez dado de alta.")
        driver = DriverService(conn).find_by_dni("12345678Z")
        assert driver.hired_on == date(2021, 9, 15)
        assert table_texts(ui.tblDrivers, 1) == ["Gómez Pérez"]
        assert ui.tblDrivers.selectionModel().selectedRows()[0].row() == 0
        assert window.invoicing.ui.cmbInvoiceDriver.findData(driver.id) > 0  # invoicing updated

    def test_validation_error_focuses_field(self, window, prompts, qtbot):
        window.show()
        ui = window.ui
        ui.mainTabs.setCurrentIndex(0)
        fill_driver_form(ui, phone="123")
        ui.btnDriverRegister.click()
        assert prompts.last == ("warning", "El teléfono debe tener 9 dígitos.")
        qtbot.waitUntil(lambda: ui.txtDriverPhone.hasFocus())

    @pytest.mark.parametrize(
        "overrides, message",
        [
            ({"salary": ""}, "El campo «Salario» es obligatorio."),
            (
                {"hired_on": "31/02/2024"},
                "Fecha no válida: «31/02/2024». Usa el formato dd/mm/aaaa.",
            ),
            ({"hired_on": ""}, "La fecha de alta es obligatoria."),
            ({"municipality": ""}, "El campo «Localidad» es obligatorio."),
        ],
    )
    def test_register_errors(self, window, prompts, overrides, message):
        fill_driver_form(window.ui, **overrides)
        window.ui.btnDriverRegister.click()
        assert prompts.last == ("warning", message)

    def test_duplicate_dni(self, window, prompts, conn):
        DriverService(conn).register(make_driver())
        fill_driver_form(window.ui)
        window.ui.btnDriverRegister.click()
        assert prompts.last == ("warning", "Ya existe un conductor con ese DNI.")

    def test_select_update_and_no_changes(self, window, prompts, conn):
        DriverService(conn).register(make_driver())
        window.drivers.refresh()
        ui = window.ui
        click_row(ui.tblDrivers, 0)
        assert ui.txtDriverDni.text() == "12345678Z"
        assert ui.cmbDriverMunicipality.currentText() == "Vigo"
        assert ui.chkLicenseA.isChecked() and ui.chkLicenseB.isChecked()

        ui.btnDriverUpdate.click()
        assert prompts.last == ("info", "No se han modificado los datos.")

        ui.txtDriverAddress.setText("Nova 3")
        ui.btnDriverUpdate.click()
        assert prompts.last == ("info", "Datos del conductor modificados.")
        assert DriverService(conn).find_by_dni("12345678Z").address == "Nova 3"

    def test_update_without_selection(self, window, prompts):
        window.ui.btnDriverUpdate.click()
        assert prompts.last == ("warning", "Selecciona un conductor de la tabla para modificarlo.")

    def test_deactivate_and_reactivate(self, window, prompts, conn):
        driver = DriverService(conn).register(make_driver())
        window.drivers.refresh()
        ui = window.ui
        click_row(ui.tblDrivers, 0)
        ui.txtDriverLeftOn.setText("31/01/2024")
        ui.btnDriverDeactivate.click()

        assert prompts.last == ("info", "Conductor dado de baja.")
        stored = DriverService(conn).get(driver.id)
        assert stored.left_on == date(2024, 1, 31)
        assert stored.hired_on == date(2021, 9, 15)  # bug D3
        assert ui.rbtDriversInactive.isChecked()  # filter follows the record
        assert ui.btnDriverDeactivate.text() == "Reactivar"
        assert not ui.driverLeftOnFrame.isHidden()

        ui.btnDriverDeactivate.click()
        assert prompts.last == ("info", "Conductor dado de alta de nuevo.")
        assert DriverService(conn).get(driver.id).is_active
        assert ui.btnDriverDeactivate.text() == "Baja"

    def test_deactivate_defaults_to_today(self, window, conn):
        driver = DriverService(conn).register(make_driver())
        window.drivers.refresh()
        click_row(window.ui.tblDrivers, 0)
        window.ui.btnDriverDeactivate.click()
        assert DriverService(conn).get(driver.id).left_on == date.today()

    def test_search(self, window, prompts, conn):
        DriverService(conn).register(make_driver(left_on=None))
        ui = window.ui
        ui.txtDriverDni.setText("00000000T")
        ui.btnDriverSearch.click()
        assert prompts.last == ("warning", "No existe ningún conductor con el DNI 00000000T.")

        ui.txtDriverDni.setText("12345678z")
        ui.btnDriverSearch.click()
        assert ui.txtDriverName.text() == "Ana"
        assert ui.lblDriverIdValue.text() != ""

    def test_status_filter(self, window, conn):
        service = DriverService(conn)
        service.register(make_driver(dni="12345678Z", surname="Activo"))
        inactive = service.register(make_driver(dni="00000000T", surname="Inactivo"))
        service.deactivate(inactive.id)
        ui = window.ui
        ui.rbtDriversAll.click()
        assert table_texts(ui.tblDrivers, 1) == ["Activo", "Inactivo"]
        ui.rbtDriversInactive.click()
        assert table_texts(ui.tblDrivers, 1) == ["Inactivo"]
        assert table_texts(ui.tblDrivers, 5) == [date.today().strftime("%d/%m/%Y")]
        ui.rbtDriversActive.click()
        assert table_texts(ui.tblDrivers, 1) == ["Activo"]

    def test_dni_check_icon(self, window):
        ui = window.ui
        ui.txtDriverDni.setText("12345678Z")
        assert not ui.lblDriverDniCheck.pixmap().isNull()
        ui.txtDriverDni.setText("")
        assert ui.lblDriverDniCheck.pixmap().isNull()

    def test_calendar_buttons(self, window, prompts):
        ui = window.ui
        ui.txtDriverHiredOn.setText("15/09/2021")
        prompts.dates.append(date(2022, 3, 4))
        ui.btnDriverHiredOnCalendar.click()
        assert prompts.calendar_opened_on[-1] == date(2021, 9, 15)
        assert ui.txtDriverHiredOn.text() == "04/03/2022"

        ui.txtDriverLeftOn.setText("not a date")
        ui.btnDriverLeftOnCalendar.click()  # cancelled
        assert prompts.calendar_opened_on[-1] is None
        assert ui.txtDriverLeftOn.text() == "not a date"


class TestClientsTab:
    def fill(self, ui, **overrides):
        values = {
            "dni": "53854586V",
            "company": "So Factive",
            "address": "Estrela 1",
            "province": "Pontevedra",
            "municipality": "Cangas",
            "phone": "619669207",
        } | overrides
        ui.txtClientDni.setText(values["dni"])
        ui.txtClientCompanyName.setText(values["company"])
        ui.txtClientAddress.setText(values["address"])
        ui.cmbClientProvince.setCurrentText(values["province"])
        ui.cmbClientMunicipality.setCurrentText(values["municipality"])
        ui.txtClientPhone.setText(values["phone"])

    def test_register_update_deactivate_reactivate(self, window, prompts, conn):
        ui = window.ui
        self.fill(ui)
        ui.btnClientRegister.click()
        assert prompts.last == ("info", "Cliente So Factive dado de alta.")
        assert table_texts(ui.tblClients, 1) == ["So Factive"]

        ui.btnClientUpdate.click()
        assert prompts.last == ("info", "No se han modificado los datos.")
        ui.txtClientPhone.setText("986000000")
        ui.btnClientUpdate.click()
        assert prompts.last == ("info", "Datos del cliente modificados.")

        ui.btnClientDeactivate.click()
        assert prompts.last == ("info", "Cliente dado de baja.")
        assert ClientService(conn).find_by_dni("53854586V").left_on == date.today()
        assert ui.btnClientDeactivate.text() == "Reactivar"

        ui.btnClientDeactivate.click()
        assert prompts.last == ("info", "Cliente dado de alta de nuevo.")

    def test_errors(self, window, prompts, conn):
        ui = window.ui
        ui.btnClientUpdate.click()
        assert prompts.last == ("warning", "Selecciona un cliente de la tabla para modificarlo.")
        ui.btnClientDeactivate.click()
        assert prompts.last == ("warning", "Selecciona un cliente de la tabla para darlo de baja.")
        self.fill(ui, company="")
        ui.btnClientRegister.click()
        assert prompts.last == ("warning", "El campo «Razón social» es obligatorio.")

    def test_select_and_search(self, window, prompts, conn):
        ClientService(conn).register(make_client())
        window.clients.refresh()
        ui = window.ui
        click_row(ui.tblClients, 0)
        assert ui.cmbClientMunicipality.currentText() == "Cangas"
        window.clients.clear()
        assert ui.txtClientDni.text() == ""
        ui.txtClientDni.setText("53854586v")
        ui.btnClientSearch.click()
        assert ui.txtClientCompanyName.text() == "So Factive"
        assert not ui.lblClientDniCheck.pixmap().isNull()

    def test_leave_date_calendar(self, window, prompts):
        prompts.dates.append(date(2024, 2, 20))
        window.ui.btnClientLeftOnCalendar.click()
        assert window.ui.txtClientLeftOn.text() == "20/02/2024"
        window.ui.btnClientLeftOnCalendar.click()  # cancelled: unchanged
        assert window.ui.txtClientLeftOn.text() == "20/02/2024"

    def test_status_filter(self, window, conn):
        service = ClientService(conn)
        service.register(make_client(dni="53854586V", company_name="Activa"))
        inactive = service.register(make_client(dni="00000000T", company_name="Inactiva"))
        service.deactivate(inactive.id)
        ui = window.ui
        ui.rbtClientsAll.click()
        assert table_texts(ui.tblClients, 1) == ["Activa", "Inactiva"]
        assert ui.clientLeftOnFrame.isHidden()
        ui.rbtClientsInactive.click()
        assert table_texts(ui.tblClients, 1) == ["Inactiva"]
        assert not ui.clientLeftOnFrame.isHidden()
