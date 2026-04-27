from PySide6.QtCore import QCoreApplication, QTimer

from .._overseer import OVERSEER
from .._root import QtQpRoot


def test_QCoreApplication_launch() -> None:
    QtQpRoot.setup_application(
        name="test_QCoreApplication",
        gui_capability="windowing",
        version="0",
        display_name=None,
        owner_name="test_owner",
        website="test.com"
    )

    if OVERSEER.state.qt_application_configured is False:
        raise Exception("Overseer 'qt_application_configured' state not updated to True")
    
    with QtQpRoot:
        app = QCoreApplication.instance()
        if app is None:
            raise Exception("QApp is not instantiated.")

        setattr(app, "successful_shutdown", False)  # noqa: B010
        app.aboutToQuit.connect(lambda: setattr(app, "successful_shutdown", True))
        
        timer1 = QTimer()
        timer1.setSingleShot(True)
        timer1.timeout.connect(QtQpRoot.shutdown_application)
        timer1.start(500)

        timer2 = QTimer()
        timer2.setSingleShot(True)
        timer2.timeout.connect(lambda: print("QApplication is running!"))
        timer2.start(250)

        QtQpRoot.run_application()

    if not getattr(app, "successful_shutdown"):  # noqa: B009
        raise Exception("not successful_shutdown")

