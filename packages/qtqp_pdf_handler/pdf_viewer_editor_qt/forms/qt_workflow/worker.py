"""Background worker for form extraction and filling tasks."""


from PySide6.QtCore import QObject, Signal, Slot  # type: ignore

from ..backend import PdfFormBackendCoordinator
from ..models import FormSchema, UserInputValues


class PdfFormWorker(QObject):
    """Worker that runs backend coordinator calls on a background thread."""

    extract_ready = Signal(str, object)  # (job_id, FormSchema)
    extract_failed = Signal(str, str)    # (job_id, message)
    fill_ready = Signal(str, object)     # (job_id, bytes)
    fill_failed = Signal(str, str)       # (job_id, message)

    def __init__(self, backend: PdfFormBackendCoordinator) -> None:
        super().__init__()
        self._backend: PdfFormBackendCoordinator = backend

    @Slot()
    def do_cancel(self, job_id: str) -> None:
        """Cancel a job cooperatively."""
        self._backend.cancel(job_id)

    @Slot()
    def do_extract(self, job_id: str, pdf_bytes_obj: object) -> None:
        """Run extraction and emit success/failure (or suppress if canceled)."""
        if not isinstance(pdf_bytes_obj, (bytes, bytearray)):
            self.extract_failed.emit(job_id, "Invalid PDF bytes.")
            return

        pdf_bytes: bytes = bytes(pdf_bytes_obj)
        result = self._backend.run("extract", job_id=job_id, pdf_bytes=pdf_bytes)
        if result is None:
            return

        if not result.ok:
            self.extract_failed.emit(job_id, result.error or "Unknown error")
            return

        schema = result.payload
        
        if schema is None:
            self.extract_failed.emit(job_id, "Backend returned no schema.")
            return
        
        assert isinstance(schema, FormSchema)
        self.extract_ready.emit(job_id, schema)

    @Slot()
    def do_fill(self, job_id: str, pdf_bytes_obj: object, values_obj: UserInputValues) -> None:
        """Run fill and emit success/failure (or suppress if canceled)."""
        if not isinstance(pdf_bytes_obj, (bytes, bytearray)):
            self.fill_failed.emit(job_id, "Invalid PDF bytes.")
            return

        if not isinstance(values_obj, dict):
            self.fill_failed.emit(job_id, "Invalid values.")
            return

        pdf_bytes: bytes = bytes(pdf_bytes_obj)
        values = values_obj

        result = self._backend.run("fill", job_id=job_id, pdf_bytes=pdf_bytes, values=values)
        if result is None:
            return

        if not result.ok:
            self.fill_failed.emit(job_id, result.error or "Unknown error")
            return

        filled_bytes = result.payload
        if filled_bytes is None:
            self.fill_failed.emit(job_id, "Backend returned no filled PDF bytes.")
            return

        assert isinstance(filled_bytes, bytes)
        self.fill_ready.emit(job_id, filled_bytes)
