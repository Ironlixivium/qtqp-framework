"""Enumeration of editor tool identifiers."""

from enum import Enum, auto
from typing import ClassVar, Protocol

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent

from .._context import EditorContext


class ToolId(Enum):
    SELECT = auto()
    RECT = auto()
    TEXT_BOX = auto()
    STAMP = auto()

class Tool(Protocol):
    """Structural protocol for tool compatibility checks."""
    _id: ClassVar[ToolId]

    @property
    def id(self) -> ToolId: ...

    def on_mouse_press(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool: ...

    def on_mouse_move(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool: ...

    def on_mouse_release(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool: ...

    def on_key_press(self, ctx: EditorContext, key_event: QKeyEvent) -> bool: ...

    def reset_interaction(self) -> None: ...