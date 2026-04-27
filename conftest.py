import sys

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("test_suite")
    yield app