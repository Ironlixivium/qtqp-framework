"""Tool for drawing rectangle annotations."""

import uuid
from typing import TYPE_CHECKING, ClassVar, cast

from PySide6.QtCore import Qt

from ....._color import Color
from ..._context import EditorContext
from ...commands import AddMarkupCommand
from ...geometry import PtRect
from ...markups import RectMarkup
from .._draw_rect_base import DrawRectToolBase
from .._typing import Tool, ToolId


class RectTool(DrawRectToolBase):
    _id: ClassVar[ToolId] = ToolId.RECT

    def _pen_color(self) -> Qt.GlobalColor:
        return Qt.GlobalColor.blue

    def _commit(self, ctx: EditorContext, page_index: int, rect: PtRect) -> None:
        ann = RectMarkup(
            id=uuid.uuid4().hex,
            page_index=page_index,
            rect=rect,
            stroke_color=Color(red=0, green=0, blue=0, alpha=255),
            stroke_width=1.0,
            fill_color=Color(red=0, green=0, blue=0, alpha=0),
        )
        ctx.undo_stack.push(AddMarkupCommand(ann))

if TYPE_CHECKING:
    _protocol_check: Tool = cast(RectTool, None)