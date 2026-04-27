"""Render request lifecycle management.

RenderCoordinator owns all bookkeeping around issuing, deduplicating, and
receiving render requests.  The widget delegates the render-related work here
so that widget.py can focus on layout, navigation, and the public API.
"""

import math
from collections.abc import Callable

from PySide6.QtCore import QRectF, QSizeF
from PySide6.QtGui import QPixmap

from ..services._doc_cache import Document
from ._scene import PdfScene
from ._state import ViewState
from ._viewport import PdfViewport
from .backends import BackendController
from .contracts import (
    RenderFailure,
    RenderKey,
    RenderRequest,
    RenderResult,
)


class RenderCoordinator:
    """Manages render requests on behalf of PdfViewWidget.

    The coordinator is stateless with respect to view layout — it reads what it
    needs from the scene, viewport, and the current ViewState via the callables
    supplied at construction time.

    Args:
        scene: The scene whose page items receive finished pixmaps.
        viewport: Used to query the visible rect and device pixel ratio.
        get_state: Callable returning the current ViewState.
        max_render_pixels_per_page: Upper pixel-count guard for large pages.
    """

    def __init__(
        self,
        scene: PdfScene,
        viewport: PdfViewport,
        get_state: Callable[[], ViewState],
        max_render_pixels_per_page: int = 20_000_000,
    ) -> None:
        """Create a coordinator bound to a scene/viewport and a state getter."""
        self._scene = scene
        self._viewport = viewport
        self._get_state = get_state
        self._max_render_pixels_per_page = max_render_pixels_per_page

        self._doc: Document | None = None
        self._backend: BackendController | None = None

        self._latest_key_for_page: dict[int, RenderKey] = {}
        self._pending_request_ids: set[str] = set()
        self._pending_request_id_to_page: dict[str, int] = {}
        self._pending_request_id_to_key: dict[str, RenderKey] = {}
        self._pending_key_counts: dict[RenderKey, int] = {}

    # ---- provider attachment ----

    def attach_provider(self, doc: Document, backend: BackendController) -> None:
        """Attach a new document + backend, disconnecting any previous one."""
        self.detach_provider()
        self._doc = doc
        self._backend = backend
        self._backend.render_done.connect(self._on_render_done)

    def detach_provider(self) -> None:
        """Cancel all outstanding requests and disconnect the current provider."""
        self.cancel_all()
        if self._backend is not None:
            try:
                self._backend.render_done.disconnect(self._on_render_done)
            except (TypeError, RuntimeError):
                pass
        self._doc = None
        self._backend = None

    # ---- public interface ----

    def request_visible_pages(self, page_rects: list[QRectF], *, force: bool) -> None:
        """Request renders for visible pages and their immediate neighbors.

        Args:
            page_rects: Current list of page rects in scene coordinates.
            force: If True, re-request even when a matching pixmap exists.
        """
        if self._doc is None or self._backend is None:
            return

        visible = self._viewport.visible_scene_rect()
        visible_pages = [i for i, rect in enumerate(page_rects) if rect.intersects(visible)]

        prefetch: set[int] = set(visible_pages)
        for i in visible_pages:
            if i - 1 >= 0:
                prefetch.add(i - 1)
            if i + 1 < self._doc.page_count:
                prefetch.add(i + 1)

        for rid, page_index in list(self._pending_request_id_to_page.items()):
            if page_index not in prefetch:
                self._backend.cancel(rid)
                self._drop_pending(rid)

        for page_index in sorted(prefetch):
            self._request_page(page_index, force=force)

    def cancel_all(self) -> None:
        """Cancel all outstanding requests and clear bookkeeping."""
        if self._backend is not None:
            for rid in list(self._pending_request_ids):
                self._backend.cancel(rid)
        for rid in list(self._pending_request_ids):
            self._drop_pending(rid)
        self._latest_key_for_page.clear()

    def invalidate(self, page_rects: list[QRectF]) -> None:
        """Clear scene pixmaps and re-request everything visible."""
        self.cancel_all()
        self._scene.clear_all_pixmaps()
        self.request_visible_pages(page_rects, force=True)

    # ---- internals ----

    def _request_page(self, page_index: int, *, force: bool) -> None:
        """Compute a render key for ``page_index`` and dispatch if needed."""
        if self._doc is None or self._backend is None:
            return

        page_item = self._scene.page_item(page_index)
        if page_item is None:
            return

        state: ViewState = self._get_state()
        dpr = self._device_pixel_ratio()
        target_dpi_unclamped = self._target_dpi_for_zoom(state.zoom, dpr)
        page_size_pt = page_item.page_rect().size()
        target_dpi = self._clamp_dpi_to_pixel_budget(page_size_pt, target_dpi_unclamped)

        key = RenderKey(
            doc_uid=self._doc.uid,
            page_index=page_index,
            zoom=float(state.zoom),
            rotation_deg=int(state.rotation_deg),
            target_dpi=float(target_dpi),
        )

        if not force:
            last = self._latest_key_for_page.get(page_index)
            if last == key and page_item.has_pixmap():
                return

        if self._pending_key_counts.get(key, 0) > 0:
            return

        req = RenderRequest(
            doc=self._doc,
            key=key,
            page_size_pt=page_size_pt,
            device_pixel_ratio=dpr,
        )
        self._mark_pending(req.request_id, page_index, key)
        self._latest_key_for_page[page_index] = key
        self._backend.request(req)

    def _on_render_done(self, result_obj: object) -> None:
        """Backend callback: apply results and clear pending bookkeeping."""
        if isinstance(result_obj, RenderResult):
            self._apply_render_result(result_obj)
        elif isinstance(result_obj, RenderFailure):
            if result_obj.request_id in self._pending_request_ids:
                self._drop_pending(result_obj.request_id)

    def _apply_render_result(self, result: RenderResult) -> None:
        """Apply a successful render result to the scene if still current."""
        if self._doc is None:
            return
        if result.request_id not in self._pending_request_ids:
            return

        self._drop_pending(result.request_id)

        if result.key.doc_uid != self._doc.uid:
            return

        page_index = result.key.page_index
        if self._latest_key_for_page.get(page_index) != result.key:
            return

        item = self._scene.page_item(page_index)
        if item is None:
            return

        pix = QPixmap.fromImage(result.image)
        if result.device_pixel_ratio:
            try:
                pix.setDevicePixelRatio(float(result.device_pixel_ratio))
            except Exception:
                pass
        item.set_pixmap(pix)

    def _mark_pending(self, request_id: str, page_index: int, key: RenderKey) -> None:
        """Record a request as pending and increment key reference counts."""
        self._pending_request_ids.add(request_id)
        self._pending_request_id_to_page[request_id] = page_index
        self._pending_request_id_to_key[request_id] = key
        self._pending_key_counts[key] = self._pending_key_counts.get(key, 0) + 1

    def _drop_pending(self, request_id: str) -> None:
        """Remove a request from pending sets/maps and decrement key counts."""
        if request_id not in self._pending_request_ids:
            return
        self._pending_request_ids.discard(request_id)
        self._pending_request_id_to_page.pop(request_id, None)
        key = self._pending_request_id_to_key.pop(request_id, None)
        if key is None:
            return
        count = self._pending_key_counts.get(key, 0) - 1
        if count <= 0:
            self._pending_key_counts.pop(key, None)
        else:
            self._pending_key_counts[key] = count

    # ---- DPI helpers ----

    def _device_pixel_ratio(self) -> float:
        """Return device pixel ratio for HiDPI rendering."""
        try:
            return float(self._viewport.devicePixelRatioF())
        except AttributeError:
            return float(self._viewport.devicePixelRatio())

    def _target_dpi_for_zoom(self, zoom: float, dpr: float) -> float:
        """Compute a target DPI based on zoom and device pixel ratio."""
        base = 144.0
        dpi = base * max(1.0, float(zoom)) * max(1.0, float(dpr))
        return max(72.0, min(600.0, dpi))

    def _clamp_dpi_to_pixel_budget(self, page_size_pt: QSizeF, dpi: float) -> float:
        """Reduce DPI to keep total pixels under the configured budget."""
        requested_dpi = float(dpi)
        max_pixels = max(1, int(self._max_render_pixels_per_page))
        width_px = float(page_size_pt.width()) * requested_dpi / 72.0
        height_px = float(page_size_pt.height()) * requested_dpi / 72.0
        total_pixels = width_px * height_px
        if total_pixels <= max_pixels:
            return requested_dpi
        scale = math.sqrt(max_pixels / max(1.0, total_pixels))
        return max(72.0, requested_dpi * scale)
