from __future__ import annotations

from PySide6.QtGui import QImage

from pdf_viewer_editor_qt.services._doc_cache import DocumentCache


def _bitmap_args(doc_uid: str = "u1", page: int = 0) -> tuple[str, int, float, int, float]:
    """Return (doc_uid, page_index, zoom, rotation_deg, target_dpi) for bitmap helpers."""
    return (doc_uid, page, 1.0, 0, 72.0)


def test_store_get_and_signals() -> None:
    cache = DocumentCache(max_docs=10, max_bytes=1024 * 1024)
    stored: list[str] = []

    cache.document_stored.connect(lambda d: stored.append(d.uid))

    doc = cache.store(uid="u1", doc_bytes=b"%PDF", title="t")
    assert doc.uid == "u1"
    assert cache.get("u1") is doc
    assert stored == ["u1"]


def test_max_docs_eviction_emits_signal() -> None:
    cache = DocumentCache(max_docs=1, max_bytes=1024 * 1024)
    evicted: list[str] = []
    cache.document_evicted.connect(lambda uid: evicted.append(uid))

    cache.store(uid="u1", doc_bytes=b"a")
    cache.store(uid="u2", doc_bytes=b"b")

    # Only the most recently stored doc should remain.
    assert cache.get("u1") is None
    assert cache.get("u2") is not None
    assert evicted == ["u1"]


def test_page_bitmap_get_set_and_byte_budget_eviction() -> None:
    # max_bytes=1 forces bitmap eviction immediately after storing.
    cache = DocumentCache(max_docs=1, max_bytes=1)
    cache.store(uid="u1", doc_bytes=b"a")

    args = _bitmap_args()
    img = QImage(10, 10, QImage.Format.Format_RGBA8888)
    cache.set_page_bitmap(*args, img)
    assert cache.get_page_bitmap(*args) is None  # evicted by budget


def test_history_push_undo_redo_updates_document_bytes() -> None:
    cache = DocumentCache(max_docs=1, max_bytes=1024 * 1024, history_depth=5)
    cache.store(uid="u1", doc_bytes=b"v0")

    cache.push_history("u1", b"v1")
    assert cache.get("u1").raw_bytes == b"v1"  # type: ignore[union-attr]

    undone = cache.undo("u1")
    assert undone == b"v0"
    assert cache.get("u1").raw_bytes == b"v0"  # type: ignore[union-attr]

    redone = cache.redo("u1")
    assert redone == b"v1"
    assert cache.get("u1").raw_bytes == b"v1"  # type: ignore[union-attr]


def test_set_page_bitmap_emits_page_updated_and_can_evict_bitmap() -> None:
    # Keep max_bytes tiny so the eviction pass clears bitmaps.
    cache = DocumentCache(max_docs=1, max_bytes=1)
    cache.store(uid="u1", doc_bytes=b"a")

    updates: list[tuple[str, int]] = []
    cache.page_updated.connect(lambda payload: updates.append(payload))

    args = _bitmap_args()
    img = QImage(10, 10, QImage.Format.Format_RGBA8888)
    cache.set_page_bitmap(*args, img)

    assert cache.get_page_bitmap(*args) is None  # evicted
    assert updates == [("u1", 0)]


def test_set_page_markups_sets_list_and_emits() -> None:
    cache = DocumentCache(max_docs=1, max_bytes=1024 * 1024)
    cache.store(uid="u1", doc_bytes=b"a")

    updates: list[tuple[str, int]] = []
    cache.page_updated.connect(lambda payload: updates.append(payload))

    cache.set_page_markups("u1", 0, markups=[{"k": "v"}])
    doc = cache.get("u1")
    assert doc is not None
    assert doc.get_or_create_page(0).markups == [{"k": "v"}]
    assert updates == [("u1", 0)]
