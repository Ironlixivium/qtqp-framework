"""Viewport implementation for the PDF viewer.

This module owns low-level view behavior:
- scroll/pan policy
- applying zoom transforms

The viewport is intentionally agnostic about PDFs.
"""

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QPainter, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QGraphicsView, QWidget
from qtqp.signals import QSignal


class PdfViewport(QGraphicsView):
    """A QGraphicsView tuned for displaying page images."""

    viewport_resized = QSignal[QRectF](object, qt_signal=True)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # Default to NO drag so scrollbars remain fully usable. The interaction
        # controller enables hand-drag only while Space is held.
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self._zoom: float = 1.0

    def zoom_factor(self) -> float:
        return self._zoom

    def set_zoom_factor(self, zoom: float) -> None:
        """Set the view transform scale.

        This method does not clamp; the controller/widget should clamp.
        """

        self._zoom = float(zoom)
        self.resetTransform()
        self.scale(self._zoom, self._zoom)

    def visible_scene_rect(self) -> QRectF:
        """Return the currently visible region in scene coordinates."""
        return self.mapToScene(self.viewport().rect()).boundingRect()

    def center_on_scene_point(self, pt: QPoint) -> None:
        self.centerOn(pt)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.viewport_resized.emit(self.visible_scene_rect())

    def wheelEvent(self, event: QWheelEvent) -> None:
        # Default behavior: scroll. Zoom behavior is mapped by interaction.py.
        super().wheelEvent(event)

    def set_pan_enabled(self, enabled: bool) -> None:
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if enabled else QGraphicsView.DragMode.NoDrag)

    def set_mouse_anchor_under_cursor(self, enabled: bool) -> None:
        anch = (
            QGraphicsView.ViewportAnchor.AnchorUnderMouse if enabled else QGraphicsView.ViewportAnchor.AnchorViewCenter
        )
        self.setTransformationAnchor(anch)
        self.setResizeAnchor(anch)
