"""Multiprocess backend controller.

BackendController manages a pool of worker subprocesses.  It is
PDF-library-independent: the actual rendering logic is supplied as the
``worker_entry`` callable (e.g. ``pdfium.worker_main``).

Worker pool
-----------
min_idle_workers   — minimum idle workers kept alive at all times (default 1)
max_idle_workers   — idle workers above this are culled after each poll (default 1)

Two dispatch modes:

* ``request()``      — standard pool dispatch; the worker is returned to idle
                       when the result arrives.
* ``request_once()`` — the subprocess is terminated as soon as its single
                       result is received.

Result collection
-----------------
All workers write to a single shared ``multiprocessing.Queue``.  A ``QTimer``
drains that queue on the main thread at ~60 fps and converts results into Qt
signals.

Cache integration
-----------------
``BackendController`` reads ``doc_ref`` bytes from ``DocumentCache`` when
dispatching jobs.  On success it writes rendered bitmaps back into the same
cache via ``DocumentCache.set_page_bitmap``.
"""

import logging
import multiprocessing
import uuid as _uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from multiprocessing.queues import Queue as MPQueue
from typing import cast

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QImage
from qtqp.signals import QSignal

from ...services._doc_cache import DocumentCache
from ._messages import (
    DescribeError,
    DescribeRequest,
    DescribeSuccess,
    RenderError,
    RenderRequest,
    RenderSuccess,
    RequestType,
    ShutdownConfirm,
    ShutdownRequest,
    new_request,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

type JobMessage = RenderRequest | DescribeRequest | ShutdownRequest
type ResultMessage = RenderSuccess | RenderError | DescribeSuccess | DescribeError | ShutdownConfirm
type WorkerEntry = Callable[[MPQueue[JobMessage], MPQueue[ResultMessage]], None]


@dataclass(frozen=True, slots=True)
class RenderFailed:
    request: RenderRequest
    message: str


@dataclass(frozen=True, slots=True)
class DescribeFailed:
    doc_uid: str
    message: str


@dataclass(frozen=True, slots=True)
class _Pending[T]:
    request: T
    retries: int
    one_shot: bool


# ---------------------------------------------------------------------------
# Worker slot
# ---------------------------------------------------------------------------

@dataclass
class _WorkerSlot:
    """Tracks one live worker subprocess and its request queue."""

    process: multiprocessing.Process
    request_q: MPQueue[JobMessage]
    slot_id: str = field(default_factory=lambda: _uuid.uuid4().hex[:8])
    busy: bool = False
    persistent: bool = True
    """If False the subprocess is terminated after its single result arrives."""


# ---------------------------------------------------------------------------
# BackendController
# ---------------------------------------------------------------------------

class BackendController(QObject):
    """Owns a pool of worker subprocesses for PDF rendering and describing.

    Parameters
    ----------
    worker_entry:
        Module-level callable executed inside each subprocess.
        Signature: ``(request_q, result_q) -> None``.
    doc_cache:
        Shared document cache.  ``doc_ref`` bytes are read from here when
        building jobs; render bitmaps are written back on success.
    min_idle_workers:
        Idle processes to keep alive even when there is no work (default 1).
    max_idle_workers:
        Idle processes above this count are culled after each poll cycle
        (default 1).
    Rendered bitmaps are cached inside each ``Page`` (keyed by render-key strings)
    within ``DocumentCache``.
    """

    render_failed   = QSignal[RenderFailed](object, qt=True)
    describe_failed = QSignal[DescribeFailed](object, qt=True)

    def __init__(
        self,
        *,
        worker_entry: WorkerEntry,
        doc_cache: DocumentCache,
        min_idle_workers: int = 1,
        max_idle_workers: int = 1,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._worker_entry = worker_entry
        self._doc_cache    = doc_cache
        self._min_idle     = max(0, int(min_idle_workers))
        self._max_idle     = max(self._min_idle, int(max_idle_workers))
        self._slots:       list[_WorkerSlot] = []
        self._result_q: MPQueue[ResultMessage] = multiprocessing.Queue()

        self._pending_renders:   dict[str, _Pending[RenderRequest]]   = {}
        self._pending_describes: dict[str, _Pending[DescribeRequest]] = {}
        # request_id → slot      (to free the slot when the result arrives)
        self._req_to_slot:       dict[str, _WorkerSlot] = {}

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(int(1000 / 60))    # 60 pps
        self._poll_timer.timeout.connect(self._poll_results)
        self._poll_timer.start()

        self._ensure_min_idle()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def request(self, request: RenderRequest | DescribeRequest) -> None:
        """Dispatch to the pool; the worker is returned to idle afterwards."""
        if isinstance(request, RenderRequest):
            self._dispatch_render(request, one_shot=False)
        else:
            self._dispatch_describe(request, one_shot=False)

    def request_once(self, request: RenderRequest | DescribeRequest) -> None:
        """Dispatch to a one-shot worker that exits after completing this job."""
        if isinstance(request, RenderRequest):
            self._dispatch_render(request, one_shot=True)
        else:
            self._dispatch_describe(request, one_shot=True)

    def cancel(self, request_id: str) -> None:
        """Mark a pending request as cancelled.

        The worker still finishes its job; the result is discarded on arrival
        and the slot is freed at that point.
        """
        self._pending_renders.pop(request_id, None)
        self._pending_describes.pop(request_id, None)

    def close(self) -> None:
        """Stop polling and terminate all worker subprocesses."""
        self._poll_timer.stop()
        for slot in list(self._slots):
            self._terminate_slot(slot)
        self._slots.clear()
        try:
            self._result_q.close()
            self._result_q.join_thread()
        except Exception as exc:
            logger.warning("Error closing result queue: %s", exc)

    # ------------------------------------------------------------------ #
    # Pool management
    # ------------------------------------------------------------------ #

    def _idle_slots(self) -> list[_WorkerSlot]:
        """Return all currently-idle worker slots."""
        return [s for s in self._slots if not s.busy]

    def _spawn_worker(self, *, persistent: bool) -> _WorkerSlot:
        """Start a new subprocess and register it as a slot."""
        request_q = cast(MPQueue[JobMessage], multiprocessing.Queue())
        proc = multiprocessing.Process(
            target=self._worker_entry,
            args=(request_q, self._result_q),
            daemon=True,
        )
        proc.start()
        slot = _WorkerSlot(process=proc, request_q=request_q, persistent=persistent)
        self._slots.append(slot)
        logger.debug("Spawned worker %s (persistent=%s)", slot.slot_id, persistent)
        return slot

    def _terminate_slot(self, slot: _WorkerSlot) -> None:
        """Terminate a subprocess and clean up its queue resources."""
        try:
            slot.request_q.put_nowait(new_request(RequestType.SHUTDOWN, "", b""))
        except Exception:
            pass
        slot.process.join(timeout=0.5)
        if slot.process.is_alive():
            slot.process.terminate()
            slot.process.join(timeout=0.5)
        try:
            slot.request_q.close()
            slot.request_q.join_thread()
        except Exception:
            pass
        if slot in self._slots:
            self._slots.remove(slot)
        for rid, s in list(self._req_to_slot.items()):
            if s is slot:
                self._req_to_slot.pop(rid, None)
        logger.debug("Terminated worker %s", slot.slot_id)

    def _ensure_min_idle(self) -> None:
        """Ensure at least ``min_idle_workers`` idle subprocesses exist."""
        idle = len(self._idle_slots())
        while idle < self._min_idle:
            self._spawn_worker(persistent=True)
            idle += 1

    def _cull_excess_idle(self) -> None:
        """Terminate idle workers above ``max_idle_workers``."""
        idle = self._idle_slots()
        while len(idle) > self._max_idle:
            self._terminate_slot(idle.pop(0))

    def _acquire_slot(self, *, one_shot: bool) -> _WorkerSlot:
        """Get an idle worker slot or spawn a new one."""
        for slot in self._slots:
            if not slot.busy:
                slot.busy = True
                slot.persistent = not one_shot
                return slot
        slot = self._spawn_worker(persistent=not one_shot)
        slot.busy = True
        return slot

    def _release_slot(self, slot: _WorkerSlot) -> None:
        """Return a slot to the idle pool (or terminate one-shot slots)."""
        if not slot.persistent:
            self._terminate_slot(slot)
        else:
            slot.busy = False

    # ------------------------------------------------------------------ #
    # Dispatching
    # ------------------------------------------------------------------ #

    def _dispatch_render(self, request: RenderRequest, *, one_shot: bool, _retry: int = 0) -> None:
        """Dispatch a render request to a worker."""
        doc_entry = self._doc_cache.get(request.doc_uid)
        doc_bytes = doc_entry.raw_bytes if doc_entry is not None else request.doc_bytes

        job = new_request(
            RequestType.RENDER,
            request.doc_uid,
            doc_bytes,
            page_index=request.page_index,
            zoom=request.zoom,
            rotation_deg=request.rotation_deg,
            target_dpi=request.target_dpi,
            device_pixel_ratio=request.device_pixel_ratio,
        )
        self._pending_renders[job.request_id] = _Pending(request, _retry, one_shot)
        slot = self._acquire_slot(one_shot=one_shot)
        self._req_to_slot[job.request_id] = slot
        slot.request_q.put(job)

    def _dispatch_describe(self, request: DescribeRequest, *, one_shot: bool, _retry: int = 0) -> None:
        """Dispatch a describe request to a worker."""
        doc_entry = self._doc_cache.get(request.doc_uid)
        doc_bytes = doc_entry.raw_bytes if doc_entry is not None else request.doc_bytes

        job = new_request(
            RequestType.DESCRIBE,
            request.doc_uid,
            doc_bytes,
        )
        self._pending_describes[job.request_id] = _Pending(request, _retry, one_shot)
        slot = self._acquire_slot(one_shot=one_shot)
        self._req_to_slot[job.request_id] = slot
        slot.request_q.put(job)

    # ------------------------------------------------------------------ #
    # Result polling
    # ------------------------------------------------------------------ #

    def _poll_results(self) -> None:
        """Drain the shared result queue and emit corresponding Qt signals."""
        try:
            while not self._result_q.empty():
                msg: ResultMessage = self._result_q.get_nowait()
                self._handle_result(msg)
        except Exception as exc:
            logger.warning("Poll error: %s", exc)
        self._cull_excess_idle()
        self._ensure_min_idle()

    def _handle_result(self, msg: ResultMessage) -> None:
        """Route a worker result to the correct handler and release its slot."""
        slot = self._req_to_slot.pop(msg.doc_uid, None)
        if slot is not None:
            self._release_slot(slot)

        match msg:
            case RenderSuccess():
                self._on_render_success(msg)
            case RenderError():
                self._on_render_error(msg)
            case DescribeSuccess():
                self._on_describe_success(msg)
            case DescribeError():
                self._on_describe_error(msg)
            case ShutdownConfirm():
                pass

    def _on_render_success(self, msg: RenderSuccess) -> None:
        """Convert worker byte output into a QImage and store in the doc cache."""
        pending = self._pending_renders.pop(msg.request_id, None)
        if pending is None:
            return   # cancelled

        fmt_map = {
            "RGB":  QImage.Format.Format_RGB888,
            "RGBA": QImage.Format.Format_RGBA8888,
        }
        fmt = fmt_map.get(msg.image_format, QImage.Format.Format_RGB888)
        img = QImage(msg.image, msg.width, msg.height, msg.stride, fmt).copy()
        try:
            img.setDevicePixelRatio(float(msg.device_pixel_ratio))
        except Exception:
            pass

        req = pending.request
        self._doc_cache.set_page_bitmap(
            req.doc_uid, req.page_index, req.zoom, req.rotation_deg, req.target_dpi or 0.0, img
        )

    def _on_render_error(self, msg: RenderError) -> None:
        """Retry a failed render up to MAX_RETRIES times, then emit render_failed."""
        pending = self._pending_renders.pop(msg.request_id, None)
        if pending is None:
            return   # cancelled
        if pending.retries < MAX_RETRIES:
            logger.warning("Render failed (attempt %d/%d): %s", pending.retries + 1, MAX_RETRIES, msg.text)
            self._dispatch_render(pending.request, one_shot=pending.one_shot, _retry=pending.retries + 1)
        else:
            logger.error("Render failed after %d attempts: %s", MAX_RETRIES, msg.text)
            self.render_failed.emit(RenderFailed(request=pending.request, message=msg.text))

    def _on_describe_success(self, msg: DescribeSuccess) -> None:
        """Store the described document with per-page sizes."""
        pending = self._pending_describes.pop(msg.request_id, None)
        if pending is None:
            return   # cancelled
        self._doc_cache.store(msg, pending.request.doc_bytes)

    def _on_describe_error(self, msg: DescribeError) -> None:
        """Retry a failed describe up to MAX_RETRIES times, then emit describe_failed."""
        pending = self._pending_describes.pop(msg.request_id, None)
        if pending is None:
            return   # cancelled
        if pending.retries < MAX_RETRIES:
            logger.warning("Describe failed (attempt %d/%d): %s", pending.retries + 1, MAX_RETRIES, msg.text)
            self._dispatch_describe(pending.request, one_shot=pending.one_shot, _retry=pending.retries + 1)
        else:
            logger.error("Describe failed after %d attempts: %s", MAX_RETRIES, msg.text)
            self.describe_failed.emit(DescribeFailed(doc_uid=msg.doc_uid, message=msg.text))
