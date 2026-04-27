"""Tool for placing text box annotations."""

import uuid
from typing import TYPE_CHECKING, ClassVar, cast

from PySide6.QtCore import Qt

from ....._color import Color
from ..._context import EditorContext
from ...commands import AddMarkupCommand
from ...geometry import PtRect
from ...markups import TextBoxMarkup
from .._draw_rect_base import DrawRectToolBase
from .._typing import Tool, ToolId


class TextBoxTool(DrawRectToolBase):
    _id: ClassVar[ToolId] = ToolId.TEXT_BOX

    def _pen_color(self) -> Qt.GlobalColor:
        return Qt.GlobalColor.darkGreen

    def _commit(self, ctx: EditorContext, page_index: int, rect: PtRect) -> None:
        markup_id = uuid.uuid4().hex
        markup = TextBoxMarkup(
            id=markup_id,
            page_index=page_index,
            rect=rect,
            text="",
            font_size=12,
            text_color=Color(red=0, green=0, blue=0, alpha=255),
            padding=14
        )
        ctx.undo_stack.push(AddMarkupCommand(markup))
        ctx.scene_adapter.enter_text_edit_mode(markup_id)

if TYPE_CHECKING:
    _protocol_check: Tool = cast(TextBoxTool, None)