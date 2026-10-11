"""Shared page template and table drawing for every report.

Coordinates are reportlab points from the bottom-left corner of an A4 page and match the
layout of the legacy reports.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from carteis.config import Company

LEFT, RIGHT = 50, 525  # horizontal rules span this range
FOOTER_Y = 50
_ELLIPSIS = "…"


class Align(Enum):
    LEFT = "left"
    CENTER = "center"


def fit(text: str, width: float, font: str, size: float) -> str:
    """Shorten ``text`` with an ellipsis so it fits in ``width`` points."""
    if stringWidth(text, font, size) <= width:
        return text
    while text and stringWidth(text + _ELLIPSIS, font, size) > width:
        text = text[:-1]
    return text + _ELLIPSIS


class Report:
    """A PDF whose pages all share the company header and the footer.

    ``decorate`` draws anything else that must repeat on every page (e.g. the client block
    of an invoice).
    """

    def __init__(
        self,
        path: Path,
        title: str,
        company: Company,
        generated_at: datetime,
        logo: Path | None = None,
        title_y: float = 695,
        decorate: Callable[[Canvas], None] | None = None,
    ) -> None:
        self.canvas = Canvas(str(path), pagesize=A4)
        self.canvas.setTitle(title)
        self.canvas.setAuthor(company.name)
        self._title = title
        self._company = company
        self._generated_at = generated_at
        self._logo = logo
        self._title_y = title_y
        self._decorate = decorate
        self._draw_page_frame()

    def new_page(self) -> None:
        self.canvas.showPage()
        self._draw_page_frame()

    def save(self) -> None:
        self.canvas.save()

    def _draw_page_frame(self) -> None:
        c, company = self.canvas, self._company
        c.line(LEFT, 800, RIGHT, 800)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(55, 785, company.name)
        c.drawString(240, self._title_y, self._title)
        c.line(LEFT, self._title_y - 5, RIGHT, self._title_y - 5)
        if self._logo and self._logo.is_file():
            c.drawImage(str(self._logo), 440, 725, width=45, height=45, mask="auto")
        c.setFont("Helvetica", 9)
        for y, text in (
            (770, f"CIF: {company.tax_id}"),
            (755, company.address),
            (740, company.city),
            (725, f"Teléfono: {company.phone}"),
            (710, f"e-mail: {company.email}"),
        ):
            c.drawString(55, y, text)

        c.line(LEFT, FOOTER_Y, RIGHT, FOOTER_Y)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(50, 40, self._generated_at.strftime("%d-%m-%Y %H:%M:%S"))
        c.drawString(250, 40, self._title)
        c.drawString(490, 40, f"Página {c.getPageNumber()}")
        if self._decorate:
            self._decorate(c)


@dataclass(frozen=True)
class TableColumn:
    header: str
    x: float  # left edge or centre, depending on ``align``
    width: float  # text longer than this is shortened
    align: Align = Align.LEFT


@dataclass(frozen=True)
class Table:
    columns: Sequence[TableColumn]
    header_y: float
    first_row_y: float
    bottom_y: float  # start a new page below this
    row_height: float = 20
    font_size: float = 7

    def draw(self, report: Report, rows: Iterable[Sequence[str]]) -> float:
        """Draw the header and the rows, breaking pages as needed. Returns the next free y."""
        self._draw_header(report.canvas)
        y = self.first_row_y
        for row in rows:
            if y <= self.bottom_y:
                report.new_page()
                self._draw_header(report.canvas)
                y = self.first_row_y
            report.canvas.setFont("Helvetica", self.font_size)
            for column, value in zip(self.columns, row, strict=True):
                _draw_text(report.canvas, column, y, value, "Helvetica", self.font_size)
            y -= self.row_height
        return y

    def _draw_header(self, canvas: Canvas) -> None:
        canvas.setFont("Helvetica-Bold", 9)
        for column in self.columns:
            _draw_text(canvas, column, self.header_y, column.header, "Helvetica-Bold", 9)
        canvas.line(LEFT, self.header_y - 5, RIGHT, self.header_y - 5)


def _draw_text(
    canvas: Canvas, column: TableColumn, y: float, text: str, font: str, size: float
) -> None:
    text = fit(text, column.width, font, size)
    match column.align:
        case Align.LEFT:
            canvas.drawString(column.x, y, text)
        case Align.CENTER:
            canvas.drawCentredString(column.x, y, text)
