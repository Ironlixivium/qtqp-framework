"""Application bootstrap and Qt configuration."""

import sys

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def _configure_app(app: QApplication) -> None:
    QFontDatabase.addApplicationFont(":/fonts/AtkinsonHyperlegible-Regular.ttf")
    QFontDatabase.addApplicationFont(":/fonts/AtkinsonHyperlegible-Bold.ttf")
    QFontDatabase.addApplicationFont(":/fonts/AtkinsonHyperlegible-BoldItalic.ttf")
    QFontDatabase.addApplicationFont(":/fonts/AtkinsonHyperlegible-Italic.ttf")
    app.setStyleSheet(
        """
            * {
                font-family: "Atkinson Hyperlegible";
                font-size: 12pt;
            }
        """
    )


def main() -> int:
    app = QApplication(sys.argv)
    _configure_app(app)
    win = MainWindow()
    win.showMaximized()
    return app.exec()
