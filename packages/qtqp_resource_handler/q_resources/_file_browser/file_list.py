"""Qt list model for file and directory entries."""

from collections.abc import Sequence
from typing import Final

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
)
from qtqp_path import QPath


class FileListModel(QAbstractListModel):
    """Qt list model storing (QPath, is_dir) entries.

    Roles:
        DisplayRole: bare filename
        ToolTipRole: full path string
        PATH_ROLE: QPath value
        IS_DIR_ROLE: True if the entry is a directory
    """

    PATH_ROLE: Final[int] = int(Qt.ItemDataRole.UserRole) + 1
    IS_DIR_ROLE: Final[int] = int(Qt.ItemDataRole.UserRole) + 2

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[tuple[QPath, bool]] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        """Return row count for the root level."""
        if parent is None:
            parent = QModelIndex()
        if parent.isValid():
            return 0
        return len(self._items)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> object | None:
        """Return data for a given index and role."""
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._items):
            return None
        path, is_dir = self._items[row]
        match role:
            case Qt.ItemDataRole.DisplayRole:
                return path.name
            case Qt.ItemDataRole.ToolTipRole:
                return str(path)
            case self.PATH_ROLE:
                return path
            case self.IS_DIR_ROLE:
                return is_dir
            case _:
                return None

    def roleNames(self) -> dict[int, QByteArray]:
        """Expose role names for QML and debugging."""
        names: dict[int, QByteArray] = dict(super().roleNames())
        names[self.PATH_ROLE] = QByteArray(b"path")
        names[self.IS_DIR_ROLE] = QByteArray(b"isDir")
        return names

    def set_items(self, items: Sequence[tuple[QPath, bool]]) -> None:
        """Replace all entries and reset the model."""
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def items(self) -> tuple[tuple[QPath, bool], ...]:
        """Return an immutable snapshot of current entries."""
        return tuple(self._items)

    def entry_at(self, row: int) -> tuple[QPath, bool]:
        """Return the (path, is_dir) entry at row.

        Raises:
            IndexError: If row is out of range.
        """
        return self._items[row]

    def entry_from_index(self, index: QModelIndex) -> tuple[QPath, bool] | None:
        """Return the entry for a QModelIndex, or None if invalid."""
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]
