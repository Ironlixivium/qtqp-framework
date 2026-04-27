from pdf_viewer_editor_qt._color import Color
from pdf_viewer_editor_qt._viewer.editor.commands import AddMarkupCommand, RemoveMarkupCommand, UpdateMarkupCommand
from pdf_viewer_editor_qt._viewer.editor.geometry import PtRect
from pdf_viewer_editor_qt._viewer.editor.markups import MarkupStore, RectMarkup
from pdf_viewer_editor_qt._viewer.editor.undo_stack import UndoStack


def test_undo_stack_push_undo_redo_add_remove() -> None:
    store = MarkupStore()
    store.set_document("doc-1")
    undo = UndoStack(store)

    m = RectMarkup(
        id="a",
        page_index=0,
        rect=PtRect(1, 2, 3, 4),
        stroke_color=Color(red=0, green=0, blue=0, alpha=255),
        stroke_width=1.0,
        fill_color=Color(red=0, green=0, blue=0, alpha=0),
    )

    undo.push(AddMarkupCommand(m))
    assert store.get("a") is not None
    undo.undo()
    assert store.get("a") is None
    undo.redo()
    assert store.get("a") is not None

    undo.push(RemoveMarkupCommand(m))
    assert store.get("a") is None
    undo.undo()
    assert store.get("a") is not None


def test_undo_stack_update_markup() -> None:
    store = MarkupStore()
    store.set_document("doc-1")
    undo = UndoStack(store)

    before = RectMarkup(
        id="a",
        page_index=0,
        rect=PtRect(1, 2, 3, 4),
        stroke_color=Color(red=0, green=0, blue=0, alpha=255),
        stroke_width=1.0,
        fill_color=Color(red=0, green=0, blue=0, alpha=0),
    )
    after = before.replace_rect(PtRect(10, 20, 30, 40))
    store.add(before)

    undo.push(UpdateMarkupCommand(before=before, after=after))
    assert store.get("a") == after
    undo.undo()
    assert store.get("a") == before
    undo.redo()
    assert store.get("a") == after

