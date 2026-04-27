"""Tool for placing stamp annotations."""

import uuid
from typing import TYPE_CHECKING, ClassVar, cast

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent

from ..._context import EditorContext
from ...commands import AddMarkupCommand
from ...geometry import PtRect
from ...markups import StampMarkup
from .._base import ToolBase
from .._typing import Tool, ToolId


class StampTool(ToolBase):
    _id: ClassVar[ToolId] = ToolId.STAMP

    # Default stamp size in PDF points (1 pt = 1/72 inch).
    DEFAULT_WIDTH = 144.0   # 2 inches
    DEFAULT_HEIGHT = 72.0   # 1 inch

    def __init__(self) -> None:
        self._default_size: tuple[float, float] = (self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

    def set_default_size(self, width: float, height: float) -> None:
        self._default_size = (width, height)

    def reset_interaction(self) -> None: ...

    def on_mouse_press(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool:
        if ctx.active_stamp_id is None:
            return False
        page_index = ctx.page_index_at(scene_pos)
        if page_index is None:
            return False
        page_pos = ctx.page_pos_at(page_index, scene_pos)
        if page_pos is None:
            return False
        w, h = self._default_size
        rect = PtRect(page_pos.x() - w / 2, page_pos.y() - h / 2, w, h)
        markup = StampMarkup(
            id=uuid.uuid4().hex,
            page_index=page_index,
            rect=rect,
            stamp_asset_id=ctx.active_stamp_id,
            opacity=1.0,
        )
        ctx.undo_stack.push(AddMarkupCommand(markup))
        return True

    def on_mouse_move(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool:
        return False

    def on_mouse_release(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool:
        return False

    def on_key_press(self, ctx: EditorContext, key_event: QKeyEvent) -> bool:
        return False

if TYPE_CHECKING:
    _protocol_check: Tool = cast(StampTool, None)
