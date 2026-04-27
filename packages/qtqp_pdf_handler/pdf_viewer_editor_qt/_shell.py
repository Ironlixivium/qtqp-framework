"""PdfEditorShell — a PdfViewWidget with editing actions and dialogs.

Wraps PdfViewWidget (read_only=False) and exposes high-level editing
operations that require user interaction (file dialogs, status feedback).
Embed this in a main window instead of a bare PdfViewWidget when editing
is needed.
"""

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QVBoxLayout, QWidget

from ._viewer import PdfViewWidget
from ._viewer.backends import BackendController
from ._viewer.editor import ToolId
from .services._doc_cache import Document


class PdfEditorShell(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewer = PdfViewWidget(parent=self, read_only=False)
        assert self.viewer.editor is not None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.viewer)

    # ---- viewer passthrough ----

    def set_document(self, doc: Document, backend: BackendController) -> None:
        self.viewer.set_document(doc, backend)

    def clear_document(self) -> None:
        self.viewer.clear_document()

    def document_descriptor(self) -> Document | None:
        return self.viewer.document_descriptor()

    # ---- editing mode ----

    def toggle_editing(self) -> None:
        self.viewer.set_editing_enabled(not self.viewer.is_editing_enabled())

    # ---- tool selection ----

    def set_tool(self, tool_id: ToolId) -> None:
        assert self.viewer.editor is not None
        self.viewer.editor.set_tool(tool_id)

    # ---- dialog actions ----

    def load_stamp(self) -> str | None:
        """Open a file dialog to pick a stamp image; returns error message or None."""
        assert self.viewer.editor is not None
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Stamp Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if not path:
            return None
        try:
            stamp_id = self.viewer.editor.register_stamp_file(path)
            self.viewer.editor.set_active_stamp(stamp_id)
            self.viewer.editor.set_tool(ToolId.STAMP)
            return None
        except Exception as exc:
            return f"Failed to load stamp: {exc}"

    def export_pdf(self) -> str | None:
        """Open a save dialog and export the annotated PDF; returns status message."""
        assert self.viewer.editor is not None
        doc = self.viewer.document_descriptor()
        if doc is None:
            return "No document loaded."
        default_name = f"{doc.title}-filled.pdf" if doc.title else "exported.pdf"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", default_name, "PDF Files (*.pdf)"
        )
        if not save_path:
            return None
        if not save_path.lower().endswith(".pdf"):
            save_path = f"{save_path}.pdf"
        try:
            self.viewer.editor.export_to_pdf(doc.raw_bytes, save_path)
            return f"Exported to {Path(save_path).name}."
        except Exception as exc:
            return f"Export failed: {exc}"
