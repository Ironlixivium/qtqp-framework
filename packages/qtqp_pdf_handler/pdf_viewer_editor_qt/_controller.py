"""Controller coordinating form workflow and viewer loading."""

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from ._shell import PdfEditorShell
from ._viewer.backends import BackendController
from ._viewer.backends.pdfium import worker_main
from .forms.backend import PdfFormBackendCoordinator
from .forms.qt_workflow import QtPdfFormFillWorkflow
from .forms.qt_workflow.controller import QThreadRunner
from .services._doc_cache import DocumentCache


class _Controller(QObject):
    def __init__(
        self,
        *,
        pdf_viewer: PdfEditorShell,
        dialog_parent: QWidget,
        show_status: Callable[[str], None],
    ) -> None:
        super().__init__()
        self._pending_doc_request_id: str | None = None
        self._pending_doc_uid: str | None = None

        self._pdf_viewer = pdf_viewer
        self._show_status = show_status

        self._doc_cache = DocumentCache()
        self._render_backend = BackendController(
            worker_entry=worker_main,
            doc_cache=self._doc_cache,
            parent=self,
        )
        self._form_backend = PdfFormBackendCoordinator()
        self._form_runner = QThreadRunner(backend=self._form_backend, parent=self)
        self._form_workflow = QtPdfFormFillWorkflow(
            runner=self._form_runner,
            dialog_parent=dialog_parent,
            show_status=self._show_status,
            parent=self,
        )

        self._form_workflow.failed.connect(self._on_form_workflow_failed)
        self._render_backend.describe_done.connect(self._on_describe_done)

        # TODO: wire form workflow filled_ready / unchanged_ready once the
        # resource handler API is defined — those handlers need the original
        # file bytes/uid which now live in q_resources.

    def _open_pdf_bytes(self, *, doc_uid: str, doc_ref: bytes, title: str) -> None:
        if self._pending_doc_request_id is not None:
            self._render_backend.cancel(self._pending_doc_request_id)
        req = DescribeRequest(doc_uid=doc_uid, doc_ref=doc_ref, title=title)
        self._pending_doc_request_id = req.request_id
        self._pending_doc_uid = doc_uid
        self._show_status(f"Loading {title}…")
        self._pdf_viewer.clear_document()
        self._render_backend.request(req)

    def _on_form_workflow_failed(self, message: str) -> None:
        self._show_status(message)

    def _on_describe_done(self, obj: object) -> None:
        from .services._doc_cache import Document
        if isinstance(obj, Document):
            if obj.uid != self._pending_doc_uid:
                return
            self._pdf_viewer.set_document(obj, self._render_backend)
            self._show_status(f"Loaded {obj.title}.")
        elif isinstance(obj, DescribeFailure):
            if obj.request_id != self._pending_doc_request_id:
                return
            if obj.doc_uid != self._pending_doc_uid:
                return
            self._show_status(f"Failed to load document: {obj.message}")

    def shutdown(self) -> None:
        self._form_runner.shutdown()
        self._render_backend.close()
