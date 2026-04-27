from pdf_viewer_editor_qt._color import Color
from pdf_viewer_editor_qt._viewer.editor.geometry import PtRect
from pdf_viewer_editor_qt._viewer.editor.markups import MarkupStore, RectMarkup, StoreEvent


def test_markup_store_events_and_basic_crud() -> None:
    store = MarkupStore()
    events: list[str] = []

    def on_event(e: StoreEvent) -> None:
        events.append(e["type"])

    store.add_listener(on_event)
    store.set_document("doc-1")

    m = RectMarkup(
        id="a",
        page_index=0,
        rect=PtRect(1, 2, 3, 4),
        stroke_color=Color(red=0, green=0, blue=0, alpha=255),
        stroke_width=1.0,
        fill_color=Color(red=0, green=0, blue=0, alpha=0),
    )
    store.add(m)
    assert store.get("a") is m
    store.remove("a")
    assert store.get("a") is None

    assert "reset" in events
    assert "added" in events
    assert "removed" in events

