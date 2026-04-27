from qtqp.pdf_handler._color import Color
from qtqp.pdf_handler._viewer.editor.geometry import PtRect
from qtqp.pdf_handler._viewer.editor.markups import (
    RectMarkup,
    StampMarkup,
    TextBoxMarkup,
    create_markup_from_dict,
)


def test_rect_markup_roundtrip() -> None:
    m = RectMarkup(
        id="a",
        page_index=0,
        rect=PtRect(1, 2, 3, 4),
        stroke_color=Color(red=1, green=2, blue=3, alpha=4),
        stroke_width=1.25,
        fill_color=Color(red=10, green=20, blue=30, alpha=40),
    )
    d = m.to_dict()
    m2 = create_markup_from_dict(d)
    assert isinstance(m2, RectMarkup)
    assert m2.to_dict() == d


def test_text_box_markup_roundtrip() -> None:
    m = TextBoxMarkup(
        id="t",
        page_index=1,
        rect=PtRect(0, 0, 10, 20),
        text="hello",
        font_size=13.0,
        text_color=Color(red=0, green=0, blue=0, alpha=255),
        padding=4.0,
    )
    d = m.to_dict()
    m2 = create_markup_from_dict(d)
    assert isinstance(m2, TextBoxMarkup)
    assert m2.to_dict() == d


def test_stamp_markup_roundtrip() -> None:
    m = StampMarkup(
        id="s",
        page_index=2,
        rect=PtRect(5, 6, 7, 8),
        stamp_asset_id="asset-1",
        opacity=0.5,
    )
    d = m.to_dict()
    m2 = create_markup_from_dict(d)
    assert isinstance(m2, StampMarkup)
    assert m2.to_dict() == d

