"""One repository per aggregate. Repositories take an open connection and never commit
on their own: multi-statement writes run inside :func:`carteis.data.database.transaction`.
"""

from carteis.data.repositories.clients import ClientRepository
from carteis.data.repositories.drivers import DriverRepository
from carteis.data.repositories.invoices import InvoiceRepository
from carteis.data.repositories.locations import LocationRepository

__all__ = ["ClientRepository", "DriverRepository", "InvoiceRepository", "LocationRepository"]
