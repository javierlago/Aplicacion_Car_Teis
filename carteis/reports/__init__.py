"""PDF reports drawn with reportlab. Pure functions of their data: no Qt, no database."""

from carteis.reports.documents import clients_report, drivers_report, invoice_report

__all__ = ["clients_report", "drivers_report", "invoice_report"]
