"""Adapter that syncs markups with the Qt graphics scene."""


import logging
from typing import cast

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtWidgets import QGraphicsItemGroup, QGraphicsRectItem

from ...services._doc_cache import Document
from .. import LayoutMode
from ._viewer_protocol import PdfViewerProtocol
from .geometry import PtRect
from .markups import Markup, MarkupItem, MarkupStore, StoreEvent, TextBoxMarkup
from .markups.qt_items import TextBoxItem, create_item
from .stamp_assets import StampRegistry

logger = logging.getLogger(__name__)


class SceneAdapter:
    """Synchronizes ``MarkupStore`` contents with Qt scene overlay items."""

    def __init__(self, store: MarkupStore, stamps: StampRegistry, viewer: PdfViewerProtocol) -> None:
        """Create an adapter bound to a specific viewer and store."""
        self._viewer = viewer
        self._viewer.documentChanged.connect(self.on_document_changed)
        self._viewer.layoutChanged.connect(self.sync_layout)
        self._viewer.pageChanged.connect(self._on_page_changed)
        self._store = store
        self._stamps = stamps
        self._page_groups: list[QGraphicsItemGroup] = []
        self._items: dict[str, MarkupItem] = {}
        self._pending_previews: dict[str, PtRect] = {}
        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(16)
        self._preview_timer.timeout.connect(self._flush_previews)

    def page_group(self, page_index: int) -> QGraphicsItemGroup | None:
        """Return the overlay group for a given page index (if in range)."""
        if page_index < 0 or page_index >= len(self._page_groups):
            return None
        return self._page_groups[page_index]

    def on_document_changed(self, doc: Document | None) -> None:
        """Rebuild overlay groups when the active document changes."""
        self._clear_all()
        if doc is None:
            return
        root = self._viewer.overlay_root()
        for _i in range(doc.page_count):
            group = QGraphicsItemGroup(root)
            self._page_groups.append(group)
        self.sync_layout(self._viewer.page_rects())

    def sync_layout(self, page_rects: list[QRectF]) -> None:
        """Update overlay group positions to match the current page layout."""
        for i, rect in enumerate(page_rects):
            if i >= len(self._page_groups):
                break
            self._page_groups[i].setPos(rect.topLeft())
        self._apply_single_page_visibility()

    def _apply_single_page_visibility(self) -> None:
        """Hide non-current page overlay groups when in single-page mode."""
        if self._viewer.view_state().layout_mode != LayoutMode.SINGLE:
            for group in self._page_groups:
                group.setVisible(True)
            return
        current = self._viewer.view_state().page_index
        for i, group in enumerate(self._page_groups):
            group.setVisible(i == current)

    def _on_page_changed(self, _index: int) -> None:
        """Viewer callback: update overlay visibility for single-page layout."""
        self._apply_single_page_visibility()

    def apply_store_reset(self, markups: list[Markup]) -> None:
        """Clear all scene items and recreate from the given markups."""
        self._pending_previews.clear()
        self._preview_timer.stop()
        for item in self._items.values():
            try:
                item.scene().removeItem(cast(QGraphicsRectItem, item))
            except Exception:
                logger.exception("SceneAdapter failed to remove item during apply_store_reset")
        self._items.clear()
        for markup in markups:
            self._create_or_update_item(markup)

    def apply_store_change(self, event: StoreEvent) -> None:
        """Apply an incremental store event to the scene."""
        event_type = event["type"]
        ids = event["ids"]
        if event_type == "reset":
            self.apply_store_reset(self._store.all())
            return
        for markup_id in ids:
            self._pending_previews.pop(markup_id, None)
            if event_type == "removed":
                item = self._items.pop(markup_id, None)
                if item is not None:
                    try:
                        item.scene().removeItem(cast(QGraphicsRectItem, item))
                    except Exception:
                        logger.exception("SceneAdapter failed to remove item during removed event")
                continue
            markup = self._store.get(markup_id)
            if markup is None:
                continue
            self._create_or_update_item(markup)

    def update_markup_preview(self, markup_id: str, rect: PtRect) -> None:
        """Schedule an interactive preview rect update for a markup."""
        self._pending_previews[markup_id] = rect
        if not self._preview_timer.isActive():
            self._preview_timer.start()

    def _flush_previews(self) -> None:
        """Apply batched preview updates to their corresponding items."""
        pending = dict(self._pending_previews)
        self._pending_previews.clear()
        for markup_id, rect in pending.items():
            markup = self._store.get(markup_id)
            if markup is None:
                continue
            preview = markup.replace_rect(rect)
            item = self._items.get(markup_id)
            if item is None:
                continue
            item.apply_markup(preview, stamps=self._stamps, is_interactive=True)  # type: ignore[arg-type]

    def enter_text_edit_mode(self, markup_id: str) -> None:
        """Enter inline edit mode for a text box item (if present)."""
        item = self._items.get(markup_id)
        if isinstance(item, TextBoxItem):
            self._viewer.viewport().viewport().setFocus(Qt.FocusReason.OtherFocusReason)
            item.enter_edit_mode()

    def _clear_all(self) -> None:
        """Remove all overlay items and page groups from the scene."""
        self._pending_previews.clear()
        self._preview_timer.stop()
        for item in self._items.values():
            try:
                item.scene().removeItem(cast(QGraphicsRectItem, item))
            except Exception:
                logger.exception("SceneAdapter failed to remove item during _clear_all items")
        self._items.clear()
        for group in self._page_groups:
            try:
                group.scene().removeItem(group)
            except Exception:
                logger.exception("SceneAdapter failed to remove item during _clear_all groups")
        self._page_groups.clear()

    def _create_or_update_item(self, markup: Markup) -> None:
        """Create a new Qt item for a markup or update the existing one."""
        group = self.page_group(markup.page_index)
        if group is None:
            return

        def _commit_text(text: str) -> None:
            current = self._store.get(markup.id)
            if isinstance(current, TextBoxMarkup):
                updated = TextBoxMarkup(
                    id=current.id,
                    page_index=current.page_index,
                    rect=current.rect,
                    text=text,
                    font_size=current.font_size,
                    text_color=current.text_color,
                    padding=current.padding,
                )
                self._store.update(updated)

        item = self._items.get(markup.id)
        if item is None:
            item = create_item(markup, on_commit_text=_commit_text, stamps=self._stamps)
            item.setParentItem(group)
            self._items[markup.id] = item
        item.apply_markup(markup, stamps=self._stamps, is_interactive=False)  # type: ignore[arg-type]

    def apply_markup_rect_final(self, markup_id: str, rect: PtRect) -> None:
        """Apply a final rect (non-preview) update to an existing item."""
        self._pending_previews.pop(markup_id, None)
        markup = self._store.get(markup_id)
        if markup is None:
            return
        final = markup.replace_rect(rect)
        item = self._items.get(markup_id)
        if item is None:
            return
        item.apply_markup(final, stamps=self._stamps, is_interactive=False)  # type: ignore[arg-type]
