"""Qt workflow that sequences: extract -> dialog -> fill.

This class:
    - Talks to a Qt backend runner (async/QThread layer) for extract/fill
    - Shows PdfFormDialog on the UI thread when fields exist
    - Emits simple outcome signals (filled/unchanged/canceled/failed)

This class does NOT:
    - Know about DocumentPayload (app-layer concern)
    - Manage threads (runner owns that)
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, Slot  # type: ignore
from PySide6.QtWidgets import QWidget

from ..models import FormSchema
from ..qt_ui import PdfFormDialog
from .controller import QThreadRunner


@dataclass(frozen=True, slots=True)
class WorkflowConfig:
    """Policy knobs for what to emit on cancel/error."""
    emit_original_on_cancel: bool = True
    emit_original_on_error: bool = True


class QtPdfFormFillWorkflow(QObject):
    """Qt workflow: extract -> (maybe) dialog -> fill, with outcome signals."""

    filled_ready = Signal(object)     # bytes
    unchanged_ready = Signal(object)  # bytes
    canceled = Signal()
    failed = Signal(str)

    def __init__(
        self,
        *,
        runner: QThreadRunner,
        dialog_parent: QWidget,
        show_status: Callable[[str], None] | None = None,
        config: WorkflowConfig | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._runner: QThreadRunner = runner
        self._dialog_parent: QWidget = dialog_parent
        self._show_status: Callable[[str], None] | None = show_status
        self._config: WorkflowConfig = config or WorkflowConfig()

        self._active_job_id: str | None = None
        self._active_pdf_bytes: bytes | None = None
        self._active_display_name: str = "PDF"

        self._runner.extract_ready.connect(self._on_extract_ready)
        self._runner.extract_failed.connect(self._on_extract_failed)
        self._runner.fill_ready.connect(self._on_fill_ready)
        self._runner.fill_failed.connect(self._on_fill_failed)

    def start(self, *, pdf_bytes: bytes, display_name: str = "PDF") -> None:
        """Start a new workflow for the given PDF bytes (cancels any active job)."""
        previous_job_id: str | None = self._active_job_id
        if previous_job_id is not None:
            self._runner.cancel_job(previous_job_id)

        job_id: str = uuid.uuid4().hex
        self._active_job_id = job_id
        self._active_pdf_bytes = pdf_bytes
        self._active_display_name = display_name

        self._set_status(f"Inspecting fields in {display_name}…")
        self._runner.submit_extract(job_id=job_id, pdf_bytes=pdf_bytes)

    def cancel_active(self) -> None:
        """Cancel the active job and emit an outcome immediately."""
        active_job_id: str | None = self._active_job_id
        active_pdf_bytes: bytes | None = self._active_pdf_bytes

        if active_job_id is not None:
            self._runner.cancel_job(active_job_id)

        self._active_job_id = None

        if self._config.emit_original_on_cancel and active_pdf_bytes is not None:
            self._set_status("Canceled.")
            self.unchanged_ready.emit(active_pdf_bytes)
        else:
            self._set_status("Canceled.")
            self.canceled.emit()

    def _is_stale(self, job_id: str) -> bool:
        return self._active_job_id is None or job_id != self._active_job_id

    def _set_status(self, text: str) -> None:
        status_cb: Callable[[str], None] | None = self._show_status
        if status_cb is not None:
            status_cb(text)

    @Slot(str, object)
    def _on_extract_ready(self, job_id: str, schema_obj: object) -> None:
        if self._is_stale(job_id):
            return
        if not isinstance(schema_obj, FormSchema):
            self._handle_error(job_id, "Extract returned an invalid schema object.")
            return

        pdf_bytes: bytes | None = self._active_pdf_bytes
        if pdf_bytes is None:
            return

        schema: FormSchema = schema_obj
        if schema.is_empty():
            self._set_status("No fillable fields found.")
            self.unchanged_ready.emit(pdf_bytes)
            return

        dialog: PdfFormDialog = PdfFormDialog(schema, parent=self._dialog_parent)
        accepted: bool = bool(dialog.exec())

        if not accepted:
            if self._config.emit_original_on_cancel:
                self._set_status("Canceled.")
                self.unchanged_ready.emit(pdf_bytes)
            else:
                self._set_status("Canceled.")
                self.canceled.emit()
            return

        values = dialog.values()
        self._set_status(f"Applying fields to {self._active_display_name}…")
        self._runner.submit_fill(job_id=job_id, pdf_bytes=pdf_bytes, values=values)

    @Slot(str, str)
    def _on_extract_failed(self, job_id: str, message: str) -> None:
        if self._is_stale(job_id):
            return
        self._handle_error(job_id, f"Field detection failed: {message}")

    @Slot(str, object)
    def _on_fill_ready(self, job_id: str, filled_bytes_obj: object) -> None:
        if self._is_stale(job_id):
            return
        if not isinstance(filled_bytes_obj, (bytes, bytearray)):
            self._handle_error(job_id, "Fill returned invalid PDF bytes.")
            return

        filled_bytes: bytes = bytes(filled_bytes_obj)
        self._set_status("Done.")
        self.filled_ready.emit(filled_bytes)

    @Slot(str, str)
    def _on_fill_failed(self, job_id: str, message: str) -> None:
        if self._is_stale(job_id):
            return
        self._handle_error(job_id, f"Fill failed: {message}")

    def _handle_error(self, job_id: str, message: str) -> None:
        """Emit failure, and optionally emit the original bytes as unchanged."""
        self._set_status(message)
        self.failed.emit(message)

        if not self._config.emit_original_on_error:
            return

        pdf_bytes: bytes | None = self._active_pdf_bytes
        if pdf_bytes is None:
            return
        if self._is_stale(job_id):
            return

        self.unchanged_ready.emit(pdf_bytes)