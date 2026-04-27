"""Qt backend runner for PDF form operations.

This module is the ONLY Qt layer that touches the Qt-free backend coordinator.
It owns:
    - QThread + worker QObject
    - submit_extract/submit_fill methods
    - cancellation forwarding
    - thread shutdown + standard deleteLater wiring

"""

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal

from ..backend import PdfFormBackendCoordinator
from ..models import UserInputValues
from .worker import PdfFormWorker


class QThreadRunner(QObject):
    """Owns QThread + worker; provides a Qt API for extract/fill with cancellation."""

    extract_ready = Signal(str, object)  # (job_id, FormSchema)
    extract_failed = Signal(str, str)    # (job_id, message)
    fill_ready = Signal(str, object)     # (job_id, bytes)
    fill_failed = Signal(str, str)       # (job_id, message)

    _request_cancel = Signal(str)
    _request_extract = Signal(str, object)
    _request_fill = Signal(str, object, object)

    def __init__(
        self,
        *,
        backend: PdfFormBackendCoordinator,
        parent: QObject | None = None,
        shutdown_timeout_ms: int = 1500,
    ) -> None:
        super().__init__(parent)

        self._shutdown_timeout_ms: int = int(shutdown_timeout_ms)
        self._is_shutdown: bool = False

        self._thread: QThread = QThread(self)
        self._worker = PdfFormWorker(backend=backend)
        self._worker.moveToThread(self._thread)

        # Requests -> worker (queued across threads)
        self._request_cancel.connect(self._worker.do_cancel)
        self._request_extract.connect(self._worker.do_extract)
        self._request_fill.connect(self._worker.do_fill)

        # Worker -> outward signals
        self._worker.extract_ready.connect(self.extract_ready)
        self._worker.extract_failed.connect(self.extract_failed)
        self._worker.fill_ready.connect(self.fill_ready)
        self._worker.fill_failed.connect(self.fill_failed)

        # Standard Qt cleanup wiring
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        # Make shutdown hard to forget
        self.destroyed.connect(self.shutdown)
        app: QCoreApplication | None = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

        self._thread.start()

    def submit_extract(self, *, job_id: str, pdf_bytes: bytes) -> None:
        """Queue an extract job."""
        self._request_extract.emit(job_id, pdf_bytes)

    def submit_fill(self, *, job_id: str, pdf_bytes: bytes, values: UserInputValues) -> None:
        """Queue a fill job."""
        self._request_fill.emit(job_id, pdf_bytes, dict(values))

    def cancel_job(self, job_id: str) -> None:
        """Cooperatively cancel a job."""
        self._request_cancel.emit(job_id)

    def shutdown(self) -> None:
        """Stop the worker thread (idempotent)."""
        if self._is_shutdown:
            return
        self._is_shutdown = True

        if self._thread.isRunning():
            self._thread.quit()
            finished: bool = bool(self._thread.wait(self._shutdown_timeout_ms))
            if not finished:
                self._thread.requestInterruption()
                self._thread.quit()
                self._thread.wait(self._shutdown_timeout_ms)