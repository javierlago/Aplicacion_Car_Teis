"""Business settings that used to be hard-coded across the legacy modules."""

from decimal import Decimal

# Price per kilometre, by trip type (legacy values: Facturacion.calcular_tarifa).
LOCAL_RATE = Decimal("0.20")  # same municipality
PROVINCIAL_RATE = Decimal("0.40")  # different municipality, same province
NATIONAL_RATE = Decimal("0.80")  # different province

VAT_RATE = Decimal("0.21")
