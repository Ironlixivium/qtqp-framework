"""In-memory annotation store with change notifications."""

from collections.abc import Callable, Iterable
from typing import Literal, TypedDict

from ._typing import Markup


class StoreEvent(TypedDict):
    """Change event emitted by ``MarkupStore`` listeners."""

    type: Literal["reset", "added", "updated", "removed"]
    ids: list[str]


class MarkupStore:
    """Stores markups for the active document and notifies listeners."""

    def __init__(self) -> None:
        """Create an empty store."""
        self._doc_uid: str | None = None
        self._items: dict[str, Markup] = {}
        self._listeners: list[Callable[[StoreEvent], None]] = []

    @property
    def doc_uid(self) -> str | None:
        """Return the current document UID (or None if detached)."""
        return self._doc_uid

    def add_listener(self, fn: Callable[[StoreEvent], None]) -> None:
        """Register a listener for store change events."""
        self._listeners.append(fn)

    def _emit(self, event: StoreEvent) -> None:
        """Notify listeners of a store change."""
        for fn in list(self._listeners):
            fn(event)

    def set_document(self, doc_uid: str | None) -> None:
        """Switch to a new document and reset store contents."""
        if doc_uid == self._doc_uid:
            return
        self._doc_uid = doc_uid
        self._items.clear()
        self._emit({"type": "reset", "ids": []})

    def reset(self, markups: Iterable[Markup]) -> None:
        """Replace all stored markups."""
        self._items = {markup.id: markup for markup in markups}
        self._emit({"type": "reset", "ids": list(self._items.keys())})

    def add(self, markup: Markup) -> None:
        """Insert a new markup (overwriting by id if needed)."""
        self._items[markup.id] = markup
        self._emit({"type": "added", "ids": [markup.id]})

    def update(self, markup: Markup) -> None:
        """Update an existing markup (overwriting by id)."""
        self._items[markup.id] = markup
        self._emit({"type": "updated", "ids": [markup.id]})

    def remove(self, markup_id: str) -> None:
        """Remove a markup by id (no-op if missing)."""
        if markup_id in self._items:
            self._items.pop(markup_id, None)
            self._emit({"type": "removed", "ids": [markup_id]})

    def get(self, markup_id: str) -> Markup | None:
        """Return a stored markup by id (if any)."""
        return self._items.get(markup_id)

    def all(self) -> list[Markup]:
        """Return all stored markups."""
        return list(self._items.values())

    def for_page(self, page_index: int) -> list[Markup]:
        """Return all stored markups for the given page index."""
        return [markup for markup in self._items.values() if markup.page_index == page_index]
