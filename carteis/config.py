"""Business settings that used to be hard-coded across the legacy modules."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Company:
    name: str
    tax_id: str
    address: str
    city: str
    phone: str
    email: str


# Printed in the header of every report (legacy: informes.top_informe).
COMPANY = Company(
    name="Transportes Teis",
    tax_id="A12345678",
    address="Avd Galicia 101",
    city="Vigo - 36216 - España",
    phone="986 123 456",
    email="carteis@gmail.com",
)

# Price per kilometre, by trip type (legacy values: Facturacion.calcular_tarifa).
LOCAL_RATE = Decimal("0.20")  # same municipality
PROVINCIAL_RATE = Decimal("0.40")  # different municipality, same province
NATIONAL_RATE = Decimal("0.80")  # different province

VAT_RATE = Decimal("0.21")
