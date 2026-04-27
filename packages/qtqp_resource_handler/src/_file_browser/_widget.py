"""Universal file browser widget backed by a contract + ops-provider keyring."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto

from PySide6.QtCore import (
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qtqp.path import QPath

from .._contracts import ClientContract, OpsProvider
from .file_list import FileListModel


class _Mode(Enum):
    FLAT = auto()
    NAV = auto()


class FileBrowserWidget(QWidget):
    """A file browser widget backed by a ClientContract and an OpsProvider keyring.

    Two modes:
        Flat mode: displays a searchable, recursively-listed flat file list.
            Construct via FileBrowserWidget.flat().
        Navigation mode: displays directory contents and allows navigating the
            tree. A recursive search bar is always visible; a nav bar (path
            input + Up button) is shown above it.
            Construct via FileBrowserWidget.navigating().

    In both modes, activating a file calls the injected on_selection callable.
    In navigation mode, activating a directory navigates into it instead.
    """

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._contract: ClientContract | None = None
        self._ops: OpsProvider | None = None
        self._mode: _Mode = _Mode.FLAT
        self._on_selection: Callable[[QPath], None] = lambda _: None
        self._modal: bool = True
        self._current_dir: QPath | None = None

        self._model = FileListModel(parent=self)
        self._proxy_model = QSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(0)

        self._build_ui()

    @classmethod
    def flat(
        cls,
        contract: ClientContract,
        on_selection: Callable[[QPath], None],
        *,
        ops: OpsProvider,
        modal: bool = True,
        parent: QWidget | None = None,
    ) -> FileBrowserWidget:
        """Create a flat-mode file browser.

        Args:
            contract: Client I/O contract scoping file access.
            on_selection: Called with the QPath of the activated file.
            ops: Keyring of contract-aware I/O callables.
            modal: If True, widget is intended for one-shot selection inside a dialog.
            parent: Qt parent widget.
        """
        widget = cls(parent=parent)
        widget._contract = contract
        widget._ops = ops
        widget._on_selection = on_selection
        widget._modal = modal
        widget.refresh()
        return widget

    @classmethod
    def navigating(
        cls,
        contract: ClientContract,
        start: QPath,
        on_selection: Callable[[QPath], None],
        *,
        ops: OpsProvider,
        modal: bool = True,
        parent: QWidget | None = None,
    ) -> FileBrowserWidget:
        """Create a navigation-mode file browser.

        Args:
            contract: Client I/O contract scoping file access.
            start: Initial directory path to display.
            on_selection: Called with the QPath of the activated file.
            ops: Keyring of contract-aware I/O callables.
            modal: If True, widget is intended for one-shot selection inside a dialog.
            parent: Qt parent widget.
        """
        widget = cls(parent=parent)
        widget._contract = contract
        widget._ops = ops
        widget._mode = _Mode.NAV
        widget._on_selection = on_selection
        widget._modal = modal
        widget._nav_bar.show()
        widget._navigate_to(start)
        return widget

    def refresh(self) -> None:
        """Reload from the data source (flat mode) or re-list the current directory (nav mode)."""
        if self._mode is _Mode.NAV and self._current_dir is not None:
            self._navigate_to(self._current_dir)
        elif self._ops is not None and self._contract is not None:
            self._model.set_items([(p, False) for p in self._ops.list_files(self._contract)])

    def load(self, path: QPath) -> bytes:
        """Load file bytes via the ops keyring.

        Raises:
            RuntimeError: If no ops or contract is set.
        """
        if self._ops is None or self._contract is None:
            raise RuntimeError("No ops or contract set for this widget")
        return self._ops.load(self._contract, path)

    def save_as(self, data: bytes, sub_path: str) -> QPath:
        """Save bytes via the ops keyring.

        Raises:
            RuntimeError: If no ops or contract is set.
        """
        if self._ops is None or self._contract is None:
            raise RuntimeError("No ops or contract set for this widget")
        return self._ops.save_as(self._contract, data, sub_path)

    def list_files(self) -> list[QPath]:
        """Return the current flat file list from the ops keyring."""
        if self._ops is None or self._contract is None:
            return []
        return self._ops.list_files(self._contract)

    def _navigate_to(self, path: QPath) -> None:
        assert self._ops is not None and self._contract is not None
        self._current_dir = path
        self._path_input.setText(str(path))
        self._search_box.clear()
        self._model.set_items(self._ops.list_dir_filtered(self._contract, path))

    def _go_up(self) -> None:
        if self._current_dir is None:
            return
        parent = self._current_dir.parent
        if parent != self._current_dir:
            self._navigate_to(parent)

    def _on_path_entered(self) -> None:
        path = QPath(self._path_input.text())
        if path.is_dir():
            self._navigate_to(path)

    def _on_search_changed(self, text: str) -> None:
        if self._mode is _Mode.FLAT:
            self._proxy_model.setFilterFixedString(text)
        else:
            if text and self._ops is not None and self._contract is not None and self._current_dir is not None:
                results = self._ops.list_files_under(self._contract, self._current_dir)
                self._model.set_items([(p, False) for p in results])
                self._proxy_model.setFilterFixedString(text)
            else:
                self._proxy_model.setFilterFixedString("")
                if self._current_dir is not None:
                    self._navigate_to(self._current_dir)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(6)

        self._nav_bar = QWidget(self)
        nav_layout = QHBoxLayout(self._nav_bar)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(6)
        up_button = QPushButton("↑ Up", self._nav_bar)
        up_button.clicked.connect(self._go_up)
        nav_layout.addWidget(up_button)
        self._path_input = QLineEdit(self._nav_bar)
        self._path_input.returnPressed.connect(self._on_path_entered)
        nav_layout.addWidget(self._path_input, 1)
        self._nav_bar.hide()
        root_layout.addWidget(self._nav_bar)

        search_bar = QWidget(self)
        search_layout = QHBoxLayout(search_bar)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(6)
        search_layout.addWidget(QLabel("Search:", search_bar))
        self._search_box = QLineEdit(search_bar)
        self._search_box.setPlaceholderText("Filter files...")
        self._search_box.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_box, 1)
        root_layout.addWidget(search_bar)

        self.list_view = QListView(self)
        self.list_view.setModel(self._proxy_model)
        self.list_view.setUniformItemSizes(True)
        self.list_view.activated.connect(self._on_activated)
        root_layout.addWidget(self.list_view, 1)

    def _on_activated(self, proxy_index: QModelIndex) -> None:
        if not proxy_index.isValid():
            return
        source_index = self._proxy_model.mapToSource(proxy_index)
        entry = self._model.entry_from_index(source_index)
        if entry is None:
            return
        path, is_dir = entry
        if is_dir:
            self._navigate_to(path)
        else:
            self._on_selection(path)
