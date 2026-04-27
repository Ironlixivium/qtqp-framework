"""Base classes and protocol for editor tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent

from .._context import EditorContext
from ._typing import ToolId


class ToolBase(ABC):
    """Abstract base class that all editor tools must subclass."""
    _id: ClassVar[ToolId]

    @property
    def id(self) -> ToolId:
        return self._id

    @abstractmethod
    def on_mouse_press(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool: ...

    @abstractmethod
    def on_mouse_move(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool: ...

    @abstractmethod
    def on_mouse_release(
        self, ctx: EditorContext, scene_pos: QPointF, buttons: Qt.MouseButton, modifiers: Qt.KeyboardModifier
    ) -> bool: ...

    @abstractmethod
    def on_key_press(self, ctx: EditorContext, key_event: QKeyEvent) -> bool: ...

    @abstractmethod
    def reset_interaction(self) -> None:
        """Clean up any in-progress interaction state."""
        ...
