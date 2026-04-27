"""Core editor controller for tools, annotations, and export."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QTransform
from PySide6.QtWidgets import QGraphicsTextItem

from ...services._doc_cache import Document
from ._context import EditorContext
from ._viewer_protocol import PdfViewerProtocol
from .markups import MarkupItem, MarkupStore, StoreEvent, TextBoxMarkup
from .pdf_export_service import export_pdf
from .scene_adapter import SceneAdapter
from .stamp_assets import StampRegistry
from .tools import RectTool, SelectTool, StampTool, TextBoxTool, Tool, ToolId
from .undo_stack import UndoStack

logger = logging.getLogger(__name__)


class PdfEditor(QObject):
    """Editor event filter and coordinator for tools, markup store, and export."""

    def __init__(self, viewer: PdfViewerProtocol, parent: QObject | None = None) -> None:
        """Create an editor bound to a specific viewer widget/protocol."""
        super().__init__(parent)
        self._viewer: PdfViewerProtocol = viewer
        self._enabled = False
        self._selected_id: str | None = None
        self._active_stamp_id: str | None = None

        self._store = MarkupStore()
        self._undo = UndoStack(self._store)
        self._stamps = StampRegistry()
        self._scene_adapter = SceneAdapter(self._store, self._stamps, viewer)

        self._tools: dict[ToolId, Tool] = {
            ToolId.SELECT: SelectTool(),
            ToolId.RECT: RectTool(),
            ToolId.TEXT_BOX: TextBoxTool(),
            ToolId.STAMP: StampTool(),
        }
        self._tool_id: ToolId = ToolId.SELECT

        self._store.add_listener(self._on_store_change)
        viewer.documentChanged.connect(self._on_document_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable editing interactions."""
        was_enabled = self._enabled
        self._enabled = bool(enabled)
        if was_enabled and not self._enabled:
            self._reset_all_tool_interactions()

    def set_tool(self, tool_id: ToolId) -> None:
        """Select the active editing tool."""
        if tool_id in self._tools:
            self._reset_all_tool_interactions()
            self._tool_id = tool_id

    def set_active_stamp(self, stamp_asset_id: str | None) -> None:
        """Set the active stamp asset id used by the stamp tool."""
        self._active_stamp_id = stamp_asset_id

    def set_stamp_default_size(self, width: float, height: float) -> None:
        """Configure the default stamp size used when creating new stamps."""
        stamp_tool = self._tools[ToolId.STAMP]
        assert isinstance(stamp_tool, StampTool)
        stamp_tool.set_default_size(width, height)

    def register_stamp_file(self, path: str) -> str:
        """Register a stamp image from disk and return its asset id."""
        return self._stamps.register_from_file(path)

    def export_to_pdf(self, source_pdf_bytes: bytes, output_path: str) -> None:
        """Export current annotations into a new PDF file at ``output_path``."""
        export_pdf(
            source_pdf_bytes=source_pdf_bytes,
            annotations=self._store.all(),
            resolve_stamp_path=self._stamps.resolve_path,
            output_path=output_path,
        )

    # ------------------------------------------------------------------
    # Event filter
    # ------------------------------------------------------------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Qt event filter that dispatches input to the active tool."""
        if not self._enabled:
            return False

        et = event.type()

        if et == QEvent.Type.Wheel:
            return False

        if et == QEvent.Type.KeyPress:
            focus = self._viewer.scene().focusItem()
            if isinstance(focus, QGraphicsTextItem) and focus.textInteractionFlags():
                return False
            assert isinstance(event, QKeyEvent)
            return self._dispatch_key(event)

        if et in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonDblClick,
        ):
            assert isinstance(event, QMouseEvent)
            pos = event.position().toPoint()
            scene_pos = self._viewer.viewport().mapToScene(pos)
            if self._is_editable_text_hit(scene_pos):
                return False
            return self._dispatch_mouse(et, event, scene_pos)

        return False

    # ------------------------------------------------------------------
    # Private dispatch helpers
    # ------------------------------------------------------------------

    def _dispatch_key(self, event: QKeyEvent) -> bool:
        """Dispatch a key press to the active tool."""
        tool = self._tools[self._tool_id]
        ctx = self._context()
        try:
            return tool.on_key_press(ctx, event)
        except Exception:
            logger.exception("Tool %s failed on key event", self._tool_id)
            return False

    def _dispatch_mouse(self, et: QEvent.Type, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Dispatch a mouse event to the active tool."""
        tool = self._tools[self._tool_id]
        ctx = self._context()

        if et == QEvent.Type.MouseButtonDblClick:
            ann_id = self._markup_id_at(scene_pos)
            ann = ctx.store.get(ann_id) if ann_id else None
            if isinstance(ann, TextBoxMarkup):
                ctx.scene_adapter.enter_text_edit_mode(ann_id or "")
            return False

        if et == QEvent.Type.MouseButtonPress:
            self._viewer.viewport().viewport().setFocus(Qt.FocusReason.MouseFocusReason)
            if self._tool_id == ToolId.TEXT_BOX:
                ann_id = self._markup_id_at(scene_pos)
                ann = ctx.store.get(ann_id) if ann_id else None
                if isinstance(ann, TextBoxMarkup):
                    self.set_tool(ToolId.SELECT)
                    ctx.set_selected_id(ann_id)
                    ctx.scene_adapter.enter_text_edit_mode(ann_id or "")
                    return False
            return self._call_tool(tool.on_mouse_press, ctx, scene_pos, event)

        if et == QEvent.Type.MouseMove:
            return self._call_tool(tool.on_mouse_move, ctx, scene_pos, event)

        if et == QEvent.Type.MouseButtonRelease:
            return self._call_tool(tool.on_mouse_release, ctx, scene_pos, event)

        return False

    def _call_tool(
        self,
        method: Callable[..., bool],
        ctx: EditorContext,
        scene_pos: QPointF,
        event: QMouseEvent,
    ) -> bool:
        """Call a tool method with consistent signature and error handling."""
        try:
            return method(ctx, scene_pos, event.buttons(), event.modifiers())
        except Exception:
            logger.exception("Tool %s failed on mouse event", self._tool_id)
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _markup_id_at(self, scene_pos: QPointF) -> str | None:
        """Return the id of the topmost markup item at ``scene_pos`` (if any)."""
        item = self._viewer.scene().itemAt(scene_pos, QTransform())
        while item is not None:
            if isinstance(item, MarkupItem):
                return item.id
            item = item.parentItem()
        return None

    def _is_editable_text_hit(self, scene_pos: QPointF) -> bool:
        """Return True if ``scene_pos`` hits a text item currently in edit mode."""
        item = self._viewer.scene().itemAt(scene_pos, QTransform())
        if isinstance(item, QGraphicsTextItem):
            return item.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction
        return False

    def _context(self) -> EditorContext:
        """Build the tool context for the current viewer and editor state."""
        v = self._viewer
        return EditorContext(
            store=self._store,
            undo_stack=self._undo,
            scene_adapter=self._scene_adapter,
            active_stamp_id=self._active_stamp_id,
            zoom_factor=max(0.01, v.view_state().zoom),
            page_index_at=v.page_index_at_scene_pos,
            page_pos_at=v.scene_pos_to_page_pos,
            page_rect_at=v.page_rect,
            ann_id_at=self._markup_id_at,
            set_selected_id=self._set_selected_id,
        )

    def _set_selected_id(self, ann_id: str | None) -> None:
        """Record the currently-selected markup id (if any)."""
        self._selected_id = ann_id

    def _on_document_changed(self, doc: Document | None) -> None:
        """Reset the markup store when the viewer switches documents."""
        self._reset_all_tool_interactions()
        if doc is None:
            self._store.set_document(None)
            self._store.reset([])
            return
        self._store.set_document(doc.uid)
        self._store.reset([])

    def _reset_all_tool_interactions(self) -> None:
        """Ask all tools to end any in-progress interaction state."""
        for tool in self._tools.values():
            tool.reset_interaction()

    def _on_store_change(self, event: StoreEvent) -> None:
        """Apply store changes into the scene via ``SceneAdapter``."""
        try:
            self._scene_adapter.apply_store_change(event)
        except Exception:
            logger.exception("SceneAdapter failed to apply store change")
