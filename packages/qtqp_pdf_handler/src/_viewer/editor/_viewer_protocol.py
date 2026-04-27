"""Protocol describing viewer capabilities needed by the editor."""

from typing import Protocol

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QGraphicsItemGroup, QGraphicsScene, QGraphicsView
from qtqp.signals import QSignalInstance

from ...services._doc_cache import Document
from .. import ViewState


class PdfViewerSignals(Protocol):
    """Signal surface consumed by the editor."""

    @property
    def documentChanged(self) -> QSignalInstance[Document | None]:
        """Emitted when the active document is attached/detached."""
        ...
    @property
    def layoutChanged(self) -> QSignalInstance[list[QRectF]]:
        """Emitted when page layout rectangles change."""
        ...
    @property
    def pageChanged(self) -> QSignalInstance[int]:
        """Emitted when the current page index changes."""
        ...


class PdfViewerNonSignals(Protocol):
    """Non-signal API surface consumed by the editor."""

    def viewport(self) -> QGraphicsView:
        """Return the underlying ``QGraphicsView`` used for display."""
        ...

    def scene(self) -> QGraphicsScene:
        """Return the ``QGraphicsScene`` used for pages and overlays."""
        ...

    def overlay_root(self) -> QGraphicsItemGroup:
        """Return the stable overlay root item for editor items."""
        ...

    def document_descriptor(self) -> Document | None:
        """Return the current document descriptor (if any)."""
        ...

    def page_rects(self) -> list[QRectF]:
        """Return layout rectangles for all pages in scene coordinates."""
        ...

    def view_state(self) -> ViewState:
        """Return the current view state."""
        ...

    def page_index_at_scene_pos(self, scene_pos: QPointF) -> int | None:
        """Return the page index at a scene coordinate (if any)."""
        ...

    def scene_pos_to_page_pos(self, page_index: int, scene_pos: QPointF) -> QPointF | None:
        """Convert a scene position into a page-local position."""
        ...

    def page_rect(self, page_index: int) -> QRectF | None:
        """Return the rect for a specific page index (if in range)."""
        ...


class PdfViewerProtocol(PdfViewerSignals, PdfViewerNonSignals):
    """Combined viewer protocol required by ``PdfEditor``."""
