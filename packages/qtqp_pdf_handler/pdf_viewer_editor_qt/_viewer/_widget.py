"""Public PDF viewer widget.

This is the main entry point you embed in your larger app.

Responsibilities:
- expose a stable API (set_document, set_page, set_zoom, ...)
- coordinate between the viewport, scene, and the host-provided render provider
- decide *when* to request renders (visible pages, zoom/rotation changes, etc.)

Non-responsibilities:
- no file I/O
- no PDF backend calls

Editing hook:
- `set_editing_enabled(True)` toggles the overlay root visibility
- `overlay_root()` exposes the overlay group so future tools can add items
"""

from dataclasses import replace

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt, QTimer
from PySide6.QtWidgets import QGraphicsItemGroup, QVBoxLayout, QWidget
from q_signalkit import QSignal

from ..services._doc_cache import Document
from . import _layout
from ._fit import compute_fit_zoom
from ._interaction import PdfInteractionController
from ._render_coordinator import RenderCoordinator
from ._scene import PdfScene
from ._state import FitMode, LayoutMode, ViewState
from ._viewport import PdfViewport
from .backends import BackendController
from .editor.pdf_editor import PdfEditor


class PdfViewWidget(QWidget):
    """A reusable PDF viewing widget."""

    pageChanged = QSignal[int](int, qt_signal=True)
    zoomChanged = QSignal[float](float, qt_signal=True)
    fitModeChanged = QSignal[FitMode](object, qt_signal=True)
    layoutModeChanged = QSignal[LayoutMode](object, qt_signal=True)
    editingModeChanged = QSignal[bool](bool, qt_signal=True)
    documentChanged = QSignal[Document | None](object, qt_signal=True)
    layoutChanged = QSignal[list[QRectF]](object, qt_signal=True)

    def __init__(self, parent: QWidget | None = None, *, read_only: bool = True) -> None:
        """Create a viewer widget."""
        super().__init__(parent)

        self._scene = PdfScene(self)
        self._viewport = PdfViewport(self)
        self._viewport.setScene(self._scene)

        # Input mapping
        self._interaction = PdfInteractionController(self)
        self._interaction.attach(self._viewport)
        self._interaction.attach(self._viewport.viewport())

        # Wire interaction intents -> widget behavior
        self._interaction.zoom_relative_requested.connect(self._on_zoom_relative)
        self._interaction.zoom_absolute_requested.connect(self._on_zoom_absolute)
        self._interaction.page_step_requested.connect(self._on_page_step)
        self._interaction.go_to_page_requested.connect(self._on_go_to_page)
        self._interaction.fit_mode_requested.connect(self.set_fit_mode)
        self._interaction.pan_mode_requested.connect(self._viewport.set_pan_enabled)

        # Re-render / update current page on viewport changes (coalesced)
        self._viewport_change_timer = QTimer(self)
        self._viewport_change_timer.setSingleShot(True)
        self._viewport_change_timer.timeout.connect(self._on_viewport_changed)
        self._viewport.viewport_resized.connect(self._schedule_viewport_changed)
        self._viewport.verticalScrollBar().valueChanged.connect(self._schedule_viewport_changed)
        self._viewport.horizontalScrollBar().valueChanged.connect(self._schedule_viewport_changed)

        # Layout
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._viewport)

        # State
        self._state = ViewState()
        self._page_rects: list[QRectF] = []
        self._doc: Document | None = None

        # Render coordinator owns all request lifecycle logic
        self._renderer = RenderCoordinator(
            scene=self._scene,
            viewport=self._viewport,
            get_state=lambda: self._state,
        )

        # Editing hook
        self._editing_enabled = False
        self._editor: PdfEditor | None = None
        if not read_only:
            self._editor = PdfEditor(viewer=self, parent=self)
            self._viewport.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self._viewport.viewport().setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self._viewport.installEventFilter(self._editor)
            self._viewport.viewport().installEventFilter(self._editor)
        self._scene.overlay_root().setVisible(False)

        # Guard against re-entrant viewport change handling when fit-to-view
        # updates trigger scroll bar signals.
        self._handling_viewport_change = False
        self._applying_fit_mode = False

    # ---- public API ----

    def viewport(self) -> PdfViewport:
        """Return the internal ``PdfViewport`` instance."""
        return self._viewport

    def scene(self) -> PdfScene:
        """Return the internal ``PdfScene`` instance."""
        return self._scene

    def overlay_root(self) -> QGraphicsItemGroup:
        """Return the overlay root item used for editing/annotations."""
        return self._scene.overlay_root()

    def document_descriptor(self) -> Document | None:
        """Return the current document (if any)."""
        return self._doc

    def page_rects(self) -> list[QRectF]:
        """Return defensive copies of the page layout rectangles."""
        return [QRectF(r) for r in self._page_rects]

    def page_rect(self, page_index: int) -> QRectF | None:
        """Return the layout rectangle for one page in scene coordinates."""
        if page_index < 0 or page_index >= len(self._page_rects):
            return None
        return QRectF(self._page_rects[page_index])

    def page_index_at_scene_pos(self, scene_pos: QPointF) -> int | None:
        """Return the page index containing ``scene_pos`` (if any)."""
        for i, rect in enumerate(self._page_rects):
            if rect.contains(scene_pos):
                return i
        return None

    def scene_pos_to_page_pos(self, page_index: int, scene_pos: QPointF) -> QPointF | None:
        """Convert a scene position into a page-local position."""
        rect = self.page_rect(page_index)
        if rect is None:
            return None
        return scene_pos - rect.topLeft()

    def page_pos_to_scene_pos(self, page_index: int, page_pos: QPointF) -> QPointF | None:
        """Convert a page-local position into a scene position."""
        rect = self.page_rect(page_index)
        if rect is None:
            return None
        return rect.topLeft() + page_pos

    @property
    def editor(self) -> PdfEditor | None:
        return self._editor

    def set_editing_enabled(self, enabled: bool) -> None:
        """Show/hide the overlay root and enable/disable the editor event filter."""
        if self._editor is None:
            return
        self._editing_enabled = bool(enabled)
        self._scene.overlay_root().setVisible(self._editing_enabled)
        self._editor.set_enabled(self._editing_enabled)
        self.editingModeChanged.emit(self._editing_enabled)

    def is_editing_enabled(self) -> bool:
        """Return whether editing overlay mode is enabled."""
        return self._editing_enabled

    def set_document(self, doc: Document, backend: BackendController) -> None:
        """Attach a new document + render backend.

        This resets view state to page 0, recomputes layout, and starts
        requesting visible pages. The backend must already be configured by
        the host app.

        Args:
            doc: Document with page sizes, description, and bytes.
            backend: BackendController that fulfills RenderRequest objects.
        """
        self._renderer.attach_provider(doc, backend)
        self._doc = doc

        self._state = replace(self._state, page_index=0)
        self._scene.set_pages(doc.page_sizes_pt())
        self._recompute_layout()
        self.documentChanged.emit(self._doc)
        self.layoutChanged.emit(list(self._page_rects))

        # Default behavior: fit width (good for embedding). Host can override.
        self.set_fit_mode(FitMode.FIT_WIDTH)
        self.set_page(0)
        self._renderer.request_visible_pages(self._page_rects, force=True)

    def clear_document(self) -> None:
        """Detach the current document and reset the scene/state."""
        self._renderer.detach_provider()
        self._doc = None
        self._scene.set_pages([])
        self._page_rects = []
        self.documentChanged.emit(None)
        self.layoutChanged.emit([])

    def view_state(self) -> ViewState:
        """Return the current view state."""
        return self._state

    def set_layout_mode(self, mode: LayoutMode) -> None:
        """Set single/continuous layout mode and refresh layout/renders."""
        self._state = self._state.with_layout_mode(mode)
        self.layoutModeChanged.emit(mode)
        self._recompute_layout()
        self._apply_fit_mode_if_needed()
        self._renderer.request_visible_pages(self._page_rects, force=True)

    def set_fit_mode(self, mode: FitMode) -> None:
        """Set fit mode and update zoom/renders."""
        self._state = self._state.with_fit_mode(mode)
        self.fitModeChanged.emit(mode)
        self._apply_fit_mode_if_needed()
        self._renderer.request_visible_pages(self._page_rects, force=True)

    def set_page(self, page_index: int) -> None:
        """Set the current page and center it in view."""
        if self._doc is None:
            return

        max_index = max(0, self._doc.page_count - 1)
        pi = max(0, min(int(page_index), max_index))
        self._state = self._state.with_page(pi)

        if self._state.layout_mode == LayoutMode.SINGLE:
            self._scene.set_only_page_visible(pi)
        else:
            for item in self._scene.page_items():
                item.setVisible(True)

        self.pageChanged.emit(pi)
        self._center_on_page(pi)
        self._renderer.request_visible_pages(self._page_rects, force=False)

    def set_zoom(self, zoom: float) -> None:
        """Set zoom (switching to free-zoom mode) and request rerenders."""
        self._state = self._state.with_zoom(zoom, fit_mode=FitMode.FREE)
        self.zoomChanged.emit(self._state.zoom)
        self._apply_view_transform()
        self._renderer.request_visible_pages(self._page_rects, force=False)

    def zoom_in(self) -> None:
        """Increase zoom by a fixed factor."""
        self.set_zoom(self._state.zoom * 1.1)

    def zoom_out(self) -> None:
        """Decrease zoom by a fixed factor."""
        self.set_zoom(self._state.zoom / 1.1)

    def invalidate_pages(self) -> None:
        """Clear pixmaps and re-request visible pages (does not touch host cache)."""
        self._renderer.invalidate(self._page_rects)

    # ---- internal wiring ----

    def _on_viewport_changed(self) -> None:
        """Coalesced handler for viewport/scroll changes."""
        if self._handling_viewport_change:
            return
        self._handling_viewport_change = True
        try:
            self._apply_fit_mode_if_needed()
            self._update_current_page_from_view()
            self._renderer.request_visible_pages(self._page_rects, force=False)
        finally:
            self._handling_viewport_change = False

    def _schedule_viewport_changed(self) -> None:
        """Debounce viewport change handling onto the next event loop tick."""
        if self._viewport_change_timer.isActive():
            return
        self._viewport_change_timer.start(0)

    def _on_zoom_relative(self, factor: float) -> None:
        """Interaction callback: apply a relative zoom factor."""
        self.set_zoom(self._state.zoom * float(factor))

    def _on_zoom_absolute(self, zoom: float) -> None:
        """Interaction callback: apply an absolute zoom value."""
        self.set_zoom(float(zoom))

    def _on_page_step(self, delta: int) -> None:
        """Interaction callback: step pages by ``delta``."""
        self.set_page(self._state.page_index + int(delta))

    def _on_go_to_page(self, page_index: int) -> None:
        """Interaction callback: go to a specific page (negative means last)."""
        if self._doc is None:
            return
        if page_index < 0:
            self.set_page(self._doc.page_count - 1)
        else:
            self.set_page(page_index)

    def _recompute_layout(self) -> None:
        """Recompute page rectangles and update the scene rect."""
        if self._doc is None:
            return
        self._page_rects = _layout.compute_page_rects(
            self._doc.page_sizes_pt(),
            self._state.layout_mode,
            spacing_pt=self._state.page_spacing_pt,
            margin_pt=self._state.margin_pt,
        )
        self._scene.set_layout(self._page_rects)
        scene_rect = _layout.scene_bounding_rect(self._page_rects, margin_pt=self._state.margin_pt)
        self._scene.setSceneRect(scene_rect)
        self.layoutChanged.emit(list(self._page_rects))

    def _apply_fit_mode_if_needed(self) -> None:
        """Apply fit-to-view zoom when fit mode is active."""
        if self._doc is None or not self._page_rects:
            return

        if self._state.fit_mode == FitMode.FREE:
            self._apply_view_transform()
            return

        page_item = self._scene.page_item(self._state.page_index)
        if page_item is None:
            return

        vp_size = QSizeF(self._viewport.viewport().width(), self._viewport.viewport().height())
        zoom = compute_fit_zoom(self._state.fit_mode, page_item.page_rect(), vp_size)

        if self._applying_fit_mode:
            return

        next_zoom = self._state.with_zoom(zoom, fit_mode=self._state.fit_mode).zoom
        if abs(next_zoom - self._state.zoom) < 1e-6:
            return

        self._applying_fit_mode = True
        try:
            self._state = self._state.with_zoom(next_zoom, fit_mode=self._state.fit_mode)
            self.zoomChanged.emit(self._state.zoom)
            self._apply_view_transform()
        finally:
            self._applying_fit_mode = False

    def _apply_view_transform(self) -> None:
        """Apply the current zoom to the viewport."""
        self._viewport.set_zoom_factor(self._state.zoom)

    def _center_on_page(self, page_index: int) -> None:
        """Center the view on the given page."""
        item = self._scene.page_item(page_index)
        if item is None:
            return
        rect = item.page_rect()
        visible = self._viewport.visible_scene_rect()
        self._viewport.centerOn(rect.center().x(), rect.top() + visible.height() / 2)

    def _update_current_page_from_view(self) -> None:
        """Update current page based on the view's visible center."""
        if self._doc is None or not self._page_rects:
            return

        visible = self._viewport.visible_scene_rect()
        center = visible.center()
        best_i = self._state.page_index
        best_dist = float("inf")

        for i, rect in enumerate(self._page_rects):
            if not rect.isValid() or not rect.intersects(visible):
                continue
            dist = abs(rect.center().y() - center.y())
            if dist < best_dist:
                best_dist = dist
                best_i = i

        if best_i != self._state.page_index:
            self._state = self._state.with_page(best_i)
            self.pageChanged.emit(best_i)
