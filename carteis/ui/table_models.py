"""A read-only Qt table model over a list of domain records."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QHeaderView, QPushButton, QTableView

_CENTER = Qt.AlignmentFlag.AlignCenter


@dataclass(frozen=True)
class Column[T]:
    header: str
    value: Callable[[T], Any]
    stretch: bool = False  # take the spare width; other columns fit their contents


class RecordTableModel[T](QAbstractTableModel):
    def __init__(self, columns: Sequence[Column[T]], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._columns = list(columns)
        self._records: list[T] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            value = self._columns[index.column()].value(self._records[index.row()])
            return "" if value is None else str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return _CENTER
        return None

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._columns[section].header
        return None

    def set_records(self, records: Sequence[T]) -> None:
        self.beginResetModel()
        self._records = list(records)
        self.endResetModel()

    def record(self, row: int) -> T:
        return self._records[row]

    def row_where(self, predicate: Callable[[T], bool]) -> int | None:
        return next((row for row, item in enumerate(self._records) if predicate(item)), None)


def attach_model[T](view: QTableView, columns: Sequence[Column[T]]) -> RecordTableModel[T]:
    model = RecordTableModel(columns, view)
    view.setModel(model)
    header = view.horizontalHeader()
    for index, column in enumerate(columns):
        stretch, fit = QHeaderView.ResizeMode.Stretch, QHeaderView.ResizeMode.ResizeToContents
        header.setSectionResizeMode(index, stretch if column.stretch else fit)
    return model


def add_row_buttons[T](
    view: QTableView, model: RecordTableModel[T], column: int, on_click: Callable[[T], None]
) -> None:
    """Put a delete (trash can) button in ``column`` of every row."""
    for row in range(model.rowCount()):
        record = model.record(row)
        button = QPushButton(view)
        button.setFixedSize(30, 28)
        button.setIcon(QIcon("img:papelera.png"))
        button.setToolTip("Eliminar")
        button.clicked.connect(lambda _checked=False, item=record: on_click(item))
        view.setIndexWidget(model.index(row, column), button)


def select_row(view: QTableView, row: int | None) -> None:
    if row is None:
        view.clearSelection()
        return
    view.selectRow(row)
    view.scrollTo(view.model().index(row, 0))
