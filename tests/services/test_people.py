from datetime import date

import pytest

from carteis.domain.errors import DuplicateError, InvalidStateError, NotFoundError, ValidationError
from carteis.services import ClientService, DriverService
from tests.factories import make_client, make_driver

TODAY = date(2026, 10, 11)


@pytest.fixture
def drivers(conn):
    return DriverService(conn, today=lambda: TODAY)


@pytest.fixture
def clients(conn):
    return ClientService(conn, today=lambda: TODAY)


class TestDriverService:
    def test_register_and_find(self, drivers):
        driver = drivers.register(make_driver())
        assert drivers.get(driver.id) == driver
        assert drivers.find_by_dni("12345678z") == driver
        assert drivers.list(active=True) == [driver]

    def test_register_requires_hire_date(self, drivers):
        with pytest.raises(ValidationError, match="fecha de alta") as error:
            drivers.register(make_driver(hired_on=None))
        assert error.value.field == "hired_on"

    def test_register_rejects_inactive(self, drivers):
        with pytest.raises(ValidationError, match="fecha de baja"):
            drivers.register(make_driver(left_on=date(2024, 1, 1)))

    def test_register_duplicate(self, drivers):
        # Bugs D1/D2: the legacy code overwrote the existing driver instead.
        drivers.register(make_driver(name="Ana"))
        with pytest.raises(DuplicateError):
            drivers.register(make_driver(name="Otra"))
        assert drivers.find_by_dni("12345678Z").name == "Ana"

    def test_find_unknown_dni(self, drivers):
        # Bug F1: the legacy search crashed silently.
        with pytest.raises(NotFoundError, match="No existe ningún conductor con el DNI 00000000T"):
            drivers.find_by_dni("00000000t")

    def test_find_invalid_dni(self, drivers):
        with pytest.raises(ValidationError):
            drivers.find_by_dni("123")

    def test_get_unknown(self, drivers):
        with pytest.raises(NotFoundError, match="código 99"):
            drivers.get(99)

    def test_update_reports_whether_something_changed(self, drivers):
        driver = drivers.register(make_driver())
        assert drivers.update(make_driver(id=driver.id)) is False
        assert drivers.update(make_driver(id=driver.id, address="Nova 3")) is True
        assert drivers.get(driver.id).address == "Nova 3"

    def test_update_requires_saved_record(self, drivers):
        with pytest.raises(ValidationError, match="Selecciona un conductor"):
            drivers.update(make_driver())
        with pytest.raises(NotFoundError):
            drivers.update(make_driver(id=99))

    def test_deactivate_defaults_to_today_and_keeps_hire_date(self, drivers):
        driver = drivers.register(make_driver())
        drivers.deactivate(driver.id)
        stored = drivers.get(driver.id)
        assert stored.left_on == TODAY
        assert stored.hired_on == date(2021, 9, 15)  # bug D3
        assert drivers.list(active=True) == []

    def test_deactivate_on_date_and_twice(self, drivers):
        driver = drivers.register(make_driver())
        drivers.deactivate(driver.id, on=date(2024, 5, 1))
        assert drivers.get(driver.id).left_on == date(2024, 5, 1)
        with pytest.raises(InvalidStateError):
            drivers.deactivate(driver.id)

    def test_reactivate(self, drivers):
        driver = drivers.register(make_driver())
        drivers.deactivate(driver.id)
        assert drivers.reactivate(driver.id).is_active
        assert drivers.get(driver.id).is_active
        with pytest.raises(InvalidStateError):
            drivers.reactivate(driver.id)


class TestClientService:
    def test_lifecycle(self, clients):
        client = clients.register(make_client())
        assert clients.find_by_dni("53854586v") == client
        assert clients.update(make_client(id=client.id, phone="986000000")) is True
        clients.deactivate(client.id)
        assert clients.list(active=False)[0].left_on == TODAY
        with pytest.raises(InvalidStateError, match="cliente ya está dado de baja"):
            clients.deactivate(client.id)
        clients.reactivate(client.id)
        assert clients.get(client.id).is_active

    def test_register_does_not_need_dates(self, clients):
        assert clients.register(make_client()).id is not None

    def test_unknown_dni(self, clients):
        with pytest.raises(NotFoundError, match="ningún cliente"):
            clients.find_by_dni("00000000T")
