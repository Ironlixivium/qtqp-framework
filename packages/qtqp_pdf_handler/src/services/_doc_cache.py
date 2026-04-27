"""Central document cache — the single source of truth for document state.

Every part of the app reads and writes here rather than keeping its own
copies of document data.

Structure
---------
Document          — one open document (bytes, per-page data, description)
  Page            — per-page data: rendered bitmaps keyed by render-key strings, markups
  _DocHistory     — undo/redo stack of doc_bytes snapshots
DocumentCache     — LRU pool of Documents with signals and byte-budget eviction

Eviction strategy (smarter LRU)
--------------------------------
When the byte budget is exceeded the cache evicts in two passes:
  0. Clear page bitmaps (regenerable) from least-recently-accessed documents.
  1. Evict entire documents (doc_bytes) LRU-first only if still over budget.

This keeps raw PDF bytes alive as long as possible, since losing them means
a full re-fetch from the source.

Signals (q_signalkit)
----------------------
  document_stored    — Document added or replaced
  document_evicted   — Document removed (carries doc uid)
  page_updated       — Page bitmap or markups changed (carries (uid, page_index))
"""

import logging
from collections import OrderedDict
from dataclasses import InitVar, dataclass, field
from typing import Any

from PySide6.QtCore import QSizeF
from PySide6.QtGui import QImage
from qtqp.signals import QSignal

from .._viewer.backends._messages import DescribeSuccess

logger = logging.getLogger(__name__)

def generate_render_key(zoom: float, rotation_deg: int, target_dpi: float) -> str:
    return f"Z{zoom}R{rotation_deg}P{target_dpi}"

# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

@dataclass
class Page:
    """Per-page data held inside a Document."""

    index: int
    size: QSizeF = field(default_factory=QSizeF)
    """Page dimensions in points (1/72 inch). Populated after a describe pass."""
    bitmaps: dict[str, QImage] = field(default_factory=dict[str, QImage])
    markups: list[Any] = field(default_factory=list[Any])

    def bitmap_bytes(self) -> int:
        """Approximate byte footprint of stored bitmaps."""
        n = 0
        for bm in self.bitmaps.values():
            try:
                n += bm.bytesPerLine() * bm.height()
            except Exception:
                n += 4 * 1024 * 1024  # 4 MiB fallback
        return n


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Document:
    """A cached document and all data associated with it."""
    page_sizes: InitVar[list[tuple[float, float]]]
    uid: str
    raw_bytes: bytes
    title: str = ""
    description: str = ""
    _pages: list[Page] = field(init=False)

    def __getitem__(self, key: int) -> Page:
        if not 0 <= key < len(self._pages):
            raise IndexError(key)
        return self._pages[key]

    def __post_init__(self, page_sizes: list[tuple[float, float]]) -> None:
        self._pages = [
            Page(i, size=QSizeF(float(w), float(h)))
            for i, (w, h) in enumerate(page_sizes)
        ]

    @property
    def page_count(self) -> int:
        return len(self._pages)
    
    def page_sizes_pt(self) -> list[QSizeF]:
        """Return page sizes in points, ordered by page index."""
        return [self[i].size for i in range(self.page_count)]

    def byte_footprint(self) -> int:
        """Return an approximate byte footprint for this document and its pages."""
        total = len(self.raw_bytes)
        for pg in self._pages:
            total += pg.bitmap_bytes()
        return total


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class _DocHistory:
    """Linear undo/redo stack of doc_bytes snapshots for a single document.

    Only the current position and neighbouring states are kept; branching
    history (editing after undo) discards the forward branch.
    """

    def __init__(self, initial: bytes, *, max_states: int = 10) -> None:
        self._states: list[bytes] = [initial]
        self._pos: int = 0
        self._max = max(2, int(max_states))

    @property
    def current(self) -> bytes:
        """Return the bytes at the current history position."""
        return self._states[self._pos]

    def push(self, state: bytes) -> None:
        """Record a new state, discarding any forward history."""
        self._states = self._states[: self._pos + 1]
        self._states.append(state)
        if len(self._states) > self._max:
            self._states.pop(0)
        self._pos = len(self._states) - 1

    def can_undo(self) -> bool:
        """Return True if ``undo()`` would change the current state."""
        return self._pos > 0

    def can_redo(self) -> bool:
        """Return True if ``redo()`` would change the current state."""
        return self._pos < len(self._states) - 1

    def undo(self) -> bytes:
        """Move one step back (if possible) and return the current state."""
        if self.can_undo():
            self._pos -= 1
        return self.current

    def redo(self) -> bytes:
        """Move one step forward (if possible) and return the current state."""
        if self.can_redo():
            self._pos += 1
        return self.current


# ---------------------------------------------------------------------------
# DocumentCache
# ---------------------------------------------------------------------------

class DocumentCache:
    """LRU pool of Document objects.

    Signals
    -------
    document_stored   QSignal[Document]        — document added or replaced
    document_evicted  QSignal[str]             — document removed (uid)
    page_updated      QSignal[tuple[str, int]] — page bitmap/markups changed
    """

    document_stored:  QSignal[Document]         = QSignal()
    document_evicted: QSignal[str]              = QSignal()
    page_updated:     QSignal[tuple[str, int]]  = QSignal()

    def __init__(
        self,
        *,
        max_docs: int = 20,
        max_bytes: int = 512 * 1024 * 1024,
        history_depth: int = 10,
    ) -> None:
        self._max_docs      = max(1, int(max_docs))
        self._max_bytes     = int(max_bytes)
        self._history_depth = int(history_depth)

        self._docs:        OrderedDict[str, Document] = OrderedDict()
        self._histories:   dict[str, _DocHistory]     = {}
        self._total_bytes: int = 0

    # ---- public: documents ----

    def __len__(self) -> int:
        """Return number of documents currently stored."""
        return len(self._docs)

    def store(self, msg: DescribeSuccess, doc_bytes: bytes) -> Document:
        """Create and cache a document from a successful describe response."""
        uid = msg.doc_uid
        if uid in self._docs:
            old = self._docs.pop(uid)
            self._total_bytes -= old.byte_footprint()

        doc = Document(msg.page_sizes_pt, uid=uid, raw_bytes=doc_bytes, title=msg.title)
        self._docs[uid] = doc
        self._docs.move_to_end(uid)
        self._histories[uid] = _DocHistory(doc_bytes, max_states=self._history_depth)
        self._total_bytes += len(doc_bytes)

        self._evict_if_needed()
        self.document_stored.emit(doc)
        return doc

    def get(self, uid: str) -> Document | None:
        """Return the Document for *uid*, promoting it to MRU, or None."""
        doc = self._docs.get(uid)
        if doc is None:
            return None
        self._docs.move_to_end(uid)
        return doc

    def evict(self, uid: str) -> None:
        """Remove a document from the cache unconditionally."""
        doc = self._docs.pop(uid, None)
        if doc is not None:
            self._total_bytes -= doc.byte_footprint()
        self._histories.pop(uid, None)
        self.document_evicted.emit(uid)

    def clear(self) -> None:
        """Remove all documents."""
        uids = list(self._docs.keys())
        self._docs.clear()
        self._histories.clear()
        self._total_bytes = 0
        for uid in uids:
            self.document_evicted.emit(uid)

    # ---- public: pages ----

    def get_page_bitmap(
        self, doc_uid: str, page_index: int, zoom: float, rotation_deg: int, target_dpi: float
    ) -> QImage | None:
        """Return a cached rendered image, or None."""
        doc = self._docs.get(doc_uid)
        if doc is None:
            return None
        self._docs.move_to_end(doc_uid)
        if not 0 <= page_index < doc.page_count:
            return None
        return doc[page_index].bitmaps.get(generate_render_key(zoom, rotation_deg, target_dpi))

    def set_page_bitmap(
        self, doc_uid: str, page_index: int, zoom: float, rotation_deg: int, target_dpi: float, bitmap: QImage
    ) -> None:
        """Store a rendered bitmap for a page."""
        doc = self._docs.get(doc_uid)
        if doc is None:
            return
        self._docs.move_to_end(doc_uid)

        pg = doc[page_index]
        rk = generate_render_key(zoom, rotation_deg, target_dpi)
        old_bytes = pg.bitmap_bytes()
        pg.bitmaps[rk] = bitmap
        self._total_bytes += pg.bitmap_bytes() - old_bytes

        self._evict_if_needed()
        self.page_updated.emit((doc_uid, page_index))

    def clear_all_page_bitmaps(self) -> None:
        """Drop all cached page bitmaps across all documents."""
        for doc in self._docs.values():
            for pg in doc._pages:
                freed = pg.bitmap_bytes()
                if freed:
                    pg.bitmaps.clear()
                    self._total_bytes -= freed

    def set_page_markups(self, uid: str, page_index: int, markups: list[Any]) -> None:
        """Replace the markup list for a page."""
        doc = self._docs.get(uid)
        if doc is None:
            return
        doc[page_index].markups = markups
        self.page_updated.emit((uid, page_index))

    # ---- public: history ----

    def push_history(self, uid: str, new_bytes: bytes) -> None:
        """Record a new document-bytes state for undo/redo."""
        h = self._histories.get(uid)
        if h is None:
            return
        doc = self._docs.get(uid)
        if doc is not None:
            self._total_bytes -= len(doc.raw_bytes)
            doc.raw_bytes = new_bytes
            self._total_bytes += len(new_bytes)
        h.push(new_bytes)
        self._evict_if_needed()
        if doc is not None:
            self.document_stored.emit(doc)

    def undo(self, uid: str) -> bytes | None:
        """Step back one history state; returns the restored bytes, or None."""
        h = self._histories.get(uid)
        if h is None or not h.can_undo():
            return None
        return self._apply_history(uid, h.undo())

    def redo(self, uid: str) -> bytes | None:
        """Step forward one history state; returns the restored bytes, or None."""
        h = self._histories.get(uid)
        if h is None or not h.can_redo():
            return None
        return self._apply_history(uid, h.redo())

    def can_undo(self, uid: str) -> bool:
        """Return True if the document has an undo state available."""
        h = self._histories.get(uid)
        return h is not None and h.can_undo()

    def can_redo(self, uid: str) -> bool:
        """Return True if the document has a redo state available."""
        h = self._histories.get(uid)
        return h is not None and h.can_redo()

    # ---- internals ----

    def _apply_history(self, uid: str, state: bytes) -> bytes:
        """Apply a history snapshot to the document and emit signals."""
        doc = self._docs.get(uid)
        if doc is not None:
            self._total_bytes -= len(doc.raw_bytes)
            doc.raw_bytes = state
            self._total_bytes += len(state)
            self.document_stored.emit(doc)
        return state

    def _evict_if_needed(self) -> None:
        """Apply eviction policy to stay within byte/doc limits."""
        # Pass 0 — clear page bitmaps LRU-first (bitmaps are regenerable).
        if self._total_bytes > self._max_bytes:
            for uid in list(self._docs.keys()):
                if self._total_bytes <= self._max_bytes:
                    break
                doc = self._docs[uid]
                for pg in doc._pages:
                    freed = pg.bitmap_bytes()
                    if freed:
                        pg.bitmaps.clear()
                        self._total_bytes -= freed

        # Pass 1 — evict whole documents LRU-first.
        while self._total_bytes > self._max_bytes and self._docs:
            uid = next(iter(self._docs))
            self.evict(uid)

        # Pass 2 — honour max_docs cap.
        while len(self._docs) > self._max_docs:
            uid = next(iter(self._docs))
            self.evict(uid)
