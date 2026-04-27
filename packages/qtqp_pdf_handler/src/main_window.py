"""Main window UI for the PDF viewer/editor."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ._shell import PdfEditorShell
from ._viewer.editor import ToolId
from .library_viewer.widget import PdfResourceBrowserWidget
from .services.document_factory import DocumentFactory
from .services.file_handler import PdfBytesLoader


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pdf Viewer")

        pdf_loader = PdfBytesLoader()
        pdf_factory = DocumentFactory(pdf_loader)

        self.pdf_browser = PdfResourceBrowserWidget(factory=pdf_factory)
        self.shell = PdfEditorShell()

        self._ui_setup()

        self._connect_signals()

    def _connect_signals(self) -> None:
        shell = self.shell

        self._act_edit.triggered.connect(shell.toggle_editing)
        self._act_select.triggered.connect(lambda: shell.set_tool(ToolId.SELECT))
        self._act_box.triggered.connect(lambda: shell.set_tool(ToolId.RECT))
        self._act_text.triggered.connect(lambda: shell.set_tool(ToolId.TEXT_BOX))
        self._act_stamp.triggered.connect(lambda: shell.set_tool(ToolId.STAMP))
        self._act_load_stamp.triggered.connect(
            lambda: self.status_label.setText(shell.load_stamp() or "Stamp loaded.")
        )
        self._act_export.triggered.connect(
            lambda: self.status_label.setText(shell.export_pdf() or "")
        )


    def _ui_setup(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        self._act_load_pdf_file = QAction("&Load PDF", self)
        file_menu.addAction(self._act_load_pdf_file)
        self._act_export = QAction("&Export PDF...", self)
        file_menu.addAction(self._act_export)

        edit_menu = menu_bar.addMenu("&Edit")
        self._act_edit = QAction("&Toggle Editing", self)
        edit_menu.addAction(self._act_edit)
        edit_menu.addSeparator()
        self._act_select = QAction("&Select", self)
        edit_menu.addAction(self._act_select)
        self._act_box = QAction("&Box", self)
        edit_menu.addAction(self._act_box)
        self._act_text = QAction("&Text", self)
        edit_menu.addAction(self._act_text)
        self._act_stamp = QAction("S&tamp", self)
        edit_menu.addAction(self._act_stamp)
        self._act_load_stamp = QAction("&Load Stamp...", self)
        edit_menu.addAction(self._act_load_stamp)

        central = QWidget(self)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self.main_group = QGroupBox("Workspace", central)
        self.main_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        main_layout = QVBoxLayout(self.main_group)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        self.pdf_browser.setMinimumWidth(220)
        self.pdf_browser.setMaximumWidth(320)

        self.status_label = QLabel("Ready.", central)
        small = QFont(self.status_label.font())
        small.setPointSize(max(8, small.pointSize() - 1))
        self.status_label.setFont(small)
        self.status_label.setStyleSheet("color: palette(mid);")

        main_split = QSplitter(Qt.Orientation.Horizontal, self.main_group)
        main_split.setChildrenCollapsible(False)
        main_split.addWidget(self.pdf_browser)
        main_split.addWidget(self.shell)
        main_split.setStretchFactor(0, 0)
        main_split.setStretchFactor(1, 1)
        main_split.setSizes([260, 900])

        main_layout.addWidget(main_split)
        root.addWidget(self.main_group, 1)

        bottom_row = QWidget(central)
        bottom_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bottom_layout = QHBoxLayout(bottom_row)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch(1)
        root.addWidget(bottom_row)
