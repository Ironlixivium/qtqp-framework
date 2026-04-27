"""Shared base for tools that draw a rectangle by click-drag."""

from __future__ import annotations

from abc import abstractmethod

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent, QPen
from PySide6.QtWidgets import QGraphicsRectItem

from .._context import EditorContext
from ..geometry import PtRect
from ._base import ToolBase


class DrawRectToolBase(ToolBase):
    """Base for rect-draw tools: manages preview item and delegates commit."""

    def __init__(self) -> None:
        self._page_index: int | None = None
        self._start_page_pos: QPointF | None = None
        self._preview_item: QGraphicsRectItem | None = None

    def reset_interaction(self) -> None:
        if self._preview_item is not None:
            scene = self._preview_item.scene()
            scene.removeItem(self._preview_item)
            self._preview_item = None
        self._page_index = None
        self._start_page_pos = None

    @abstractmethod
    def _pen_color(self) -> Qt.GlobalColor: ...

    def _can_start(self, ctx: EditorContext) -> bool:
        """Return False to block the tool from starting (e.g. no stamp selected)."""
        return True

    @abstractmethod
    def _commit(self, ctx: EditorContext, page_index: int, rect: PtRect) -> None:
        """Called on mouse-release with the finalised, normalised rect."""
        ...

    def on_mouse_press(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool:
        if not self._can_start(ctx):
            self.reset_interaction()
            return False
        page_index = ctx.page_index_at(scene_pos)
        if page_index is None:
            self.reset_interaction()
            return False
        page_pos = ctx.page_pos_at(page_index, scene_pos)
        if page_pos is None:
            self.reset_interaction()
            return False
        group = ctx.scene_adapter.page_group(page_index)
        if group is None:
            self.reset_interaction()
            return False
        preview_item = QGraphicsRectItem(group)
        pen = QPen(self._pen_color())
        pen.setStyle(Qt.PenStyle.DashLine)
        preview_item.setPen(pen)
        preview_item.setRect(page_pos.x(), page_pos.y(), 1.0, 1.0)
        self._page_index = page_index
        self._start_page_pos = page_pos
        self._preview_item = preview_item
        return True

    def on_mouse_move(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool:
        if self._preview_item is None or self._page_index is None or self._start_page_pos is None:
            self.reset_interaction()
            return False
        page_pos = ctx.page_pos_at(self._page_index, scene_pos)
        if page_pos is None:
            self.reset_interaction()
            return True
        rect = PtRect(
            self._start_page_pos.x(),
            self._start_page_pos.y(),
            page_pos.x() - self._start_page_pos.x(),
            page_pos.y() - self._start_page_pos.y(),
        ).normalized()
        self._preview_item.setRect(rect.x, rect.y, rect.w, rect.h)
        return True

    def on_mouse_release(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool:
        if self._preview_item is None or self._page_index is None or self._start_page_pos is None:
            self.reset_interaction()
            return False
        if not self._can_start(ctx):
            self.reset_interaction()
            return True
        page_pos = ctx.page_pos_at(self._page_index, scene_pos)
        if page_pos is None:
            self.reset_interaction()
            return True
        rect = PtRect(
            self._start_page_pos.x(),
            self._start_page_pos.y(),
            page_pos.x() - self._start_page_pos.x(),
            page_pos.y() - self._start_page_pos.y(),
        ).normalized()
        page_index = self._page_index
        self.reset_interaction()
        self._commit(ctx, page_index, rect)
        return True

    def on_key_press(self, ctx: EditorContext, key_event: QKeyEvent) -> bool:
        if key_event.key() == Qt.Key.Key_Escape and self._preview_item is not None:
            self.reset_interaction()
            return True
        return False
