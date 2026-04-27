"""Tool for selecting, moving, and resizing annotations."""

import math
from typing import TYPE_CHECKING, ClassVar, cast

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent

from ..._context import EditorContext
from ...commands import UpdateMarkupCommand
from ...geometry import PtRect
from ...markups import Markup
from .._base import ToolBase
from .._typing import Tool, ToolId


class SelectTool(ToolBase):
    _id: ClassVar[ToolId] = ToolId.SELECT

    def __init__(self) -> None:
        self._active_id: str | None = None
        self._dragging = False
        self._resize_corner: str | None = None
        self._start_scene_pos: QPointF | None = None
        self._start_rect: PtRect | None = None

    def reset_interaction(self) -> None:
        self._dragging = False
        self._active_id = None
        self._resize_corner = None
        self._start_scene_pos = None
        self._start_rect = None

    def on_mouse_press(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool:
        markup_id = ctx.ann_id_at(scene_pos)
        if not markup_id:
            ctx.set_selected_id(None)
            return False

        markup = ctx.store.get(markup_id)
        if markup is None:
            return False

        ctx.set_selected_id(markup_id)
        self._active_id = markup_id
        self._start_scene_pos = scene_pos
        self._start_rect = markup.rect
        self._resize_corner = self._pick_corner(ctx, markup, scene_pos)
        self._dragging = True
        return True

    def on_mouse_move(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool:
        if not self._dragging or self._active_id is None or self._start_rect is None or self._start_scene_pos is None:
            self.reset_interaction()
            return False

        markup = ctx.store.get(self._active_id)
        if markup is None:
            self.reset_interaction()
            return True

        new_rect = self._compute_drag_rect(ctx, markup, scene_pos)
        ctx.scene_adapter.update_markup_preview(self._active_id, new_rect)
        return True

    def on_mouse_release(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool:
        if not self._dragging or self._active_id is None or self._start_rect is None:
            self.reset_interaction()
            return False

        markup = ctx.store.get(self._active_id)
        if markup is None:
            self.reset_interaction()
            return True

        new_rect = self._compute_drag_rect(ctx, markup, scene_pos)
        if new_rect != self._start_rect:
            before = markup.replace_rect(self._start_rect)
            after = markup.replace_rect(new_rect)
            ctx.undo_stack.push(UpdateMarkupCommand(before=before, after=after))
        else:
            ctx.scene_adapter.apply_markup_rect_final(self._active_id, self._start_rect)

        self.reset_interaction()
        return True

    def on_key_press(self, ctx: EditorContext, key_event: QKeyEvent) -> bool:
        if key_event.key() == Qt.Key.Key_Escape and self._dragging:
            self.reset_interaction()
            return True
        return False

    def _pick_corner(self, ctx: EditorContext, markup: Markup, scene_pos: QPointF) -> str | None:
        page_rect = ctx.page_rect_at(markup.page_index)
        if page_rect is None:
            return None
        tolerance_scene = 8.0 / ctx.zoom_factor
        corners = {
            "tl": page_rect.topLeft() + QPointF(markup.rect.x, markup.rect.y),
            "tr": page_rect.topLeft() + QPointF(markup.rect.x + markup.rect.w, markup.rect.y),
            "bl": page_rect.topLeft() + QPointF(markup.rect.x, markup.rect.y + markup.rect.h),
            "br": page_rect.topLeft() + QPointF(markup.rect.x + markup.rect.w, markup.rect.y + markup.rect.h),
        }
        for corner, pt in corners.items():
            if math.hypot(scene_pos.x() - pt.x(), scene_pos.y() - pt.y()) <= tolerance_scene:
                return corner
        return None

    def _compute_drag_rect(self, ctx: EditorContext, markup: Markup, scene_pos: QPointF) -> PtRect:
        page_rect = ctx.page_rect_at(markup.page_index)
        if page_rect is None or self._start_scene_pos is None or self._start_rect is None:
            return markup.rect

        if self._resize_corner is None:
            dx = scene_pos.x() - self._start_scene_pos.x()
            dy = scene_pos.y() - self._start_scene_pos.y()
            return PtRect(self._start_rect.x + dx, self._start_rect.y + dy, self._start_rect.w, self._start_rect.h)

        page_pos = scene_pos - page_rect.topLeft()
        x, y, w, h = self._start_rect.x, self._start_rect.y, self._start_rect.w, self._start_rect.h
        if self._resize_corner == "tl":
            w = (x + w) - page_pos.x()
            h = (y + h) - page_pos.y()
            x = page_pos.x()
            y = page_pos.y()
        elif self._resize_corner == "tr":
            w = page_pos.x() - x
            h = (y + h) - page_pos.y()
            y = page_pos.y()
        elif self._resize_corner == "bl":
            w = (x + w) - page_pos.x()
            x = page_pos.x()
            h = page_pos.y() - y
        elif self._resize_corner == "br":
            w = page_pos.x() - x
            h = page_pos.y() - y
        return PtRect(x, y, w, h).normalized()

if TYPE_CHECKING:
    _protocol_check: Tool = cast(SelectTool, None)
