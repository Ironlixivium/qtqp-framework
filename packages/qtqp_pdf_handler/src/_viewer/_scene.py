"""Scene + items used by the PDF viewer.

This module owns how pages are represented inside a QGraphicsScene.
It does *not* decide layout (that's layout.py) and it does *not* trigger
rendering (that's widget.py).

Editing hook:
- The scene creates an overlay root item (`overlay_root()`) that can be used
  later to hold annotation/selection items without changing the page items.
"""


from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QRectF, QSizeF, Qt
from PySide6.QtGui import QBrush, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QWidget,
)


@dataclass(slots=True)
class PageStyle:
    """Simple styling knobs for page rendering in the scene."""

    background_brush: QBrush
    border_pen: QPen


def default_page_style() -> PageStyle:
    """Return the default page background/border style."""
    # Keep it minimal; host app can theme by swapping style later if desired.
    bg = QBrush(Qt.GlobalColor.white)
    pen = QPen(Qt.GlobalColor.black)
    pen.setCosmetic(True)
    pen.setWidth(1)
    return PageStyle(background_brush=bg, border_pen=pen)


class PdfPageItem(QGraphicsItemGroup):
    """A single page in the scene.

    Contains:
    - a background rect
    - a pixmap item that holds the rendered page image
    """

    def __init__(
        self, page_index: int, page_rect: QRectF, style: PageStyle, parent: QGraphicsItem | None = None
    ) -> None:
        """Create a page item with a background rect and a pixmap holder."""
        super().__init__(parent)
        self.page_index = page_index
        self._page_rect = QRectF(page_rect)

        self._bg_rect_item = QGraphicsRectItem(self._page_rect)
        self._bg_rect_item.setBrush(style.background_brush)
        self._bg_rect_item.setPen(style.border_pen)
        self._bg_rect_item.setZValue(0)

        self._pix_item = QGraphicsPixmapItem()
        self._pix_item.setZValue(1)
        # Smooth scaling in view transforms.
        self._pix_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

        self.addToGroup(self._bg_rect_item)
        self.addToGroup(self._pix_item)

        # Align pixmap top-left to page rect.
        self._pix_item.setPos(self._page_rect.topLeft())

    def page_rect(self) -> QRectF:
        """Return the page rect in scene coordinates."""
        return QRectF(self._page_rect)

    def set_page_rect(self, page_rect: QRectF) -> None:
        """Update the page rect and reposition the pixmap top-left."""
        self.prepareGeometryChange()
        self._page_rect = QRectF(page_rect)
        self._bg_rect_item.setRect(self._page_rect)
        self._pix_item.setPos(self._page_rect.topLeft())

        # If a pixmap is already set, keep it at the same top-left. The pixmap
        # itself is not automatically scaled to the new rect.

    def clear_pixmap(self) -> None:
        """Clear any rendered pixmap from this page."""
        self._pix_item.setPixmap(QPixmap())
        self._pix_item.setTransform(QTransform())  # identity

    def has_pixmap(self) -> bool:
        """Return True if a non-null pixmap is set."""
        return not self._pix_item.pixmap().isNull()

    def set_pixmap(self, pixmap: QPixmap) -> None:
        """Set the page pixmap and scale it to the page rect in scene units."""

        self._pix_item.setPixmap(pixmap)

        if pixmap.isNull():
            self._pix_item.setTransform(QTransform())
            return

        # Compute logical pixmap size (accounting for HiDPI).
        try:
            dpr = float(pixmap.devicePixelRatioF())
        except Exception:
            try:
                dpr = float(pixmap.devicePixelRatio())
            except Exception:
                dpr = 1.0

        dpr = max(1.0, dpr)
        logical_w = pixmap.width() / dpr
        logical_h = pixmap.height() / dpr
        if logical_w <= 0 or logical_h <= 0:
            self._pix_item.setTransform(QTransform())
            return

        sx = self._page_rect.width() / logical_w
        sy = self._page_rect.height() / logical_h

        t = QTransform()
        t.scale(sx, sy)
        self._pix_item.setTransform(t)

    def set_visible(self, visible: bool) -> None:
        """Compatibility shim for older call sites."""
        self.setVisible(visible)


class PdfScene(QGraphicsScene):
    """Scene holding all page items (and an overlay group for future editing)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an empty scene with a stable overlay root."""
        super().__init__(parent)
        self._page_items: list[PdfPageItem] = []
        self._page_sizes_pt: list[QSizeF] = []
        self._style = default_page_style()

        # Overlays intended for future editing/annotations.
        self._overlay_group = QGraphicsItemGroup()
        self._overlay_group.setZValue(1000)
        self.addItem(self._overlay_group)

    def overlay_root(self) -> QGraphicsItemGroup:
        """Root item for overlays/annotations.

        Keep this stable so future editing tools can add items without
        rewriting the page-render pipeline.
        """

        return self._overlay_group

    def set_page_style(self, style: PageStyle) -> None:
        """Set default style for newly-created page items."""
        self._style = style
        # Note: existing items won't update their brushes/pens automatically.
        # If you want re-theming, rebuild the scene or add methods to update.

    def set_pages(self, page_sizes_pt: Sequence[QSizeF]) -> None:
        """Create placeholder page items.

        Layout rectangles are not set here. Call set_layout(...) afterward.
        """

        # Clear page items (keep overlay root).
        for item in self._page_items:
            self.removeItem(item)

        self._page_items.clear()
        self._page_sizes_pt = [QSizeF(s) for s in page_sizes_pt]

        for i, size in enumerate(self._page_sizes_pt):
            rect = QRectF(0, 0, float(size.width()), float(size.height()))
            page_item = PdfPageItem(i, rect, self._style)
            self._page_items.append(page_item)
            self.addItem(page_item)

    def set_layout(self, page_rects: Sequence[QRectF]) -> None:
        """Update each page item's rect/position."""
        if len(page_rects) != len(self._page_items):
            raise ValueError("page_rects length must match page count")

        for item, rect in zip(self._page_items, page_rects, strict=False):
            item.set_page_rect(rect)

    def page_item(self, page_index: int) -> PdfPageItem | None:
        """Return the page item for ``page_index`` (if in range)."""
        if 0 <= page_index < len(self._page_items):
            return self._page_items[page_index]
        return None

    def page_items(self) -> list[PdfPageItem]:
        """Return a shallow copy of all page items."""
        return list(self._page_items)

    def clear_all_pixmaps(self) -> None:
        """Clear all rendered pixmaps from all pages."""
        for item in self._page_items:
            item.clear_pixmap()

    def set_only_page_visible(self, page_index: int) -> None:
        """Set visibility so only ``page_index`` is shown."""
        for i, item in enumerate(self._page_items):
            item.setVisible(i == page_index)
