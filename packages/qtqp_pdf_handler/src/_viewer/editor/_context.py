"""EditorContext — shared data passed to every tool on each event."""

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF

from .markups import MarkupStore
from .scene_adapter import SceneAdapter
from .undo_stack import UndoStack


@dataclass
class EditorContext:
    store: MarkupStore
    undo_stack: UndoStack
    scene_adapter: SceneAdapter
    active_stamp_id: str | None
    zoom_factor: float
    page_index_at: Callable[[QPointF], int | None]
    page_pos_at: Callable[[int, QPointF], QPointF | None]
    page_rect_at: Callable[[int], QRectF | None]
    ann_id_at: Callable[[QPointF], str | None]
    set_selected_id: Callable[[str | None], None]
